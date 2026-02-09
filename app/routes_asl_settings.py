from flask import jsonify, request
from flask_login import login_required, current_user
from app import app

@app.route('/api/settings/asl-mtd-filters', methods=['POST'])
@login_required
def update_asl_mtd_filters():
    """API endpoint to update ASL MTD filter settings (admin only)"""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        from app.models import AppSetting
        data = request.get_json()
        exclude_12_months = data.get('exclude_12_months', False)
        exclude_1_year = data.get('exclude_1_year', False)
        
        # Save settings
        AppSetting.set_value(
            'asl_mtd_exclude_12_months', 
            str(exclude_12_months).lower(), 
            current_user.id,
            'Exclude schools with 12+ months scholarship duration from ASL MTD'
        )
        AppSetting.set_value(
            'asl_mtd_exclude_1_year_awarded', 
            str(exclude_1_year).lower(), 
            current_user.id,
            'Exclude schools where first scholarship awarded >1 year ago from ASL MTD'
        )
        
        return jsonify({
            'success': True, 
            'message': 'ASL MTD filter settings updated successfully',
            'settings': {
                'exclude_12_months': exclude_12_months,
                'exclude_1_year': exclude_1_year
            }
        })
    except Exception as e:
        app.logger.error(f"Error updating ASL MTD settings: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/asl-mtd-filters', methods=['GET'])
@login_required
def get_asl_mtd_filters():
    """API endpoint to get current ASL MTD filter settings"""
    try:
        from app.models import AppSetting
        exclude_12_months = AppSetting.get_value('asl_mtd_exclude_12_months', 'true') == 'true'
        exclude_1_year = AppSetting.get_value('asl_mtd_exclude_1_year_awarded', 'true') == 'true'
        
        return jsonify({
            'success': True,
            'settings': {
                'exclude_12_months': exclude_12_months,
                'exclude_1_year': exclude_1_year
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting ASL MTD settings: {e}")
        return jsonify({'error': str(e)}), 500
