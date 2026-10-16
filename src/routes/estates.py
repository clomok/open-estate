"""Choosing and creating estates. These routes sit OUTSIDE /e/<slug>/ - they
pick an estate rather than read one - so none of them touches estate data."""

import os
import shutil
import subprocess
import sys

from flask import (Blueprint, current_app, flash, redirect, render_template, request,
                   session, url_for)

from src import estates
from src.services.auth_service import login_required

bp = Blueprint('estates', __name__)

UPGRADE_SCRIPT = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'upgrade_db.py')


def _root():
    return current_app.config['ESTATES_ROOT']


@bp.route('/')
@login_required
def home():
    """The bare address opens the estate used last, or the first one."""
    entry = estates.get(_root(), session.get('estate', '')) if \
        estates.SLUG_RE.match(session.get('estate', '')) else None
    entry = entry or estates.default(_root())
    if entry is None:
        return redirect(url_for('estates.new'))
    return redirect(url_for('main.now', estate=entry['slug']))


@bp.route('/estates/go')
@login_required
def go():
    """The sidebar dropdown. Switching always lands on the new estate's Now
    page: an id in the old page's URL means a different record in another
    estate, or none."""
    slug = request.args.get('slug', '')
    if slug == '__new__':
        return redirect(url_for('estates.new'))
    if not estates.SLUG_RE.match(slug) or estates.get(_root(), slug) is None:
        flash('No such estate.')
        return redirect(url_for('estates.home'))
    return redirect(url_for('main.now', estate=slug))


@bp.route('/estates/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        slug = request.form.get('slug', '').strip().lower()
        label = request.form.get('label', '').strip()
        try:
            estates.check_slug(slug)
            if estates.get(_root(), slug) is not None:
                raise estates.EstateError(f"An estate named '{slug}' already exists.")
            folder = estates.estate_dir(_root(), slug)
            if os.path.exists(folder):
                raise estates.EstateError(
                    f"instance/estates/{slug}/ already exists but is not registered. "
                    "Adopt it with scripts/estate_admin.py, or pick another name.")
            os.makedirs(folder)
            # The same migrator the container runs at start, in its own
            # process: a fresh estate gets exactly the schema and seeded rows
            # (the default playbook) that an upgraded one has.
            proc = subprocess.run(
                [sys.executable, UPGRADE_SCRIPT, '--estate', slug],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, 'ESTATES_ROOT': _root()})
            if proc.returncode != 0:
                shutil.rmtree(folder, ignore_errors=True)
                raise estates.EstateError(
                    'Could not build the new database: ' + (proc.stderr or proc.stdout)[-400:])
            estates.add(_root(), slug, label or slug)
        except estates.EstateError as e:
            flash(str(e))
            return render_template('new_estate.html', slug=slug, label=label)
        flash(f"Created estate '{label or slug}'.")
        return redirect(url_for('main.now', estate=slug))
    return render_template('new_estate.html', slug='', label='')
