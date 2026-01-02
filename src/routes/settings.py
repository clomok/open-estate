import io
import zipfile
from flask import Blueprint, render_template, send_file, request, flash, redirect, url_for
from src.services.auth_service import login_required
from src.services.export_service import generate_backup_zip
from src.services.import_service import restore_from_json

bp = Blueprint('settings', __name__, url_prefix='/settings')

@bp.route('/')
@login_required
def index():
    return render_template('settings.html')

@bp.route('/download')
@login_required
def download_backup():
    try:
        zip_buffer = generate_backup_zip()
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='estate_backup.zip'
        )
    except Exception as e:
        flash(f"Error creating backup: {str(e)}")
        return redirect(url_for('settings.index'))

@bp.route('/upload', methods=['POST'])
@login_required
def upload_backup():
    if 'backup_file' not in request.files:
        flash('No file part')
        return redirect(url_for('settings.index'))
        
    file = request.files['backup_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('settings.index'))

    if file:
        # We expect a JSON file directly OR a ZIP containing it.
        # For simplicity in V1, let's assume they upload the extracted JSON
        # or we add logic to unzip. Let's stick to JSON upload for restore for now to be safe.
        
        # Note: If you want to support restoring from the ZIP, we need to unzip here.
        # Let's try to detect.
        content = None
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(file) as z:
                # Find the json file inside
                for name in z.namelist():
                    if name.endswith('.json'):
                        content = z.read(name)
                        break
        elif file.filename.endswith('.json'):
            content = file.read()
            
        if content:
            success, msg = restore_from_json(content)
            if success:
                flash("Database restored successfully.")
            else:
                flash(f"Restore failed: {msg}")
        else:
            flash("Could not find valid JSON data in file.")
            
    return redirect(url_for('settings.index'))