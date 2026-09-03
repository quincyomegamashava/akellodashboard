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


@app.route('/api/settings/revenue-reports', methods=['POST'])
@login_required
def update_revenue_report_settings():
    """Update admin-configurable revenue report schedule and source mode."""
    if current_user.userRole != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        from app.models import AppSetting
        from app.scheduler import refresh_revenue_report_schedule

        data = request.get_json() or {}
        source_mode = (data.get('source_mode') or 'db_template').strip().lower()
        schedule_time = (data.get('schedule_time') or '06:00').strip()
        table_source = (data.get('table_source') or 'latest_generated').strip().lower()
        auto_email_enabled = bool(data.get('auto_email_enabled', False))
        email_delivery_mode = (data.get('email_delivery_mode') or 'attach_plus_summary').strip().lower()
        email_recipient_mode = (data.get('email_recipient_mode') or 'custom_group_later').strip().lower()
        email_recipients = (data.get('email_recipients') or '').strip()
        zig_exchange_raw = data.get('zig_exchange', 37)
        fy_digest_enabled = bool(data.get('fy_digest_enabled', False))
        fy_digest_time = (data.get('fy_digest_time') or '07:00').strip()
        fy_digest_period = (data.get('fy_digest_period') or 'FY2027').strip().upper() or 'FY2027'

        allowed_modes = {'db_template', 'excel_ingest_folder', 'hybrid'}
        if source_mode not in allowed_modes:
            return jsonify({'error': 'Invalid source_mode'}), 400
        if table_source not in {'latest_generated', 'template'}:
            return jsonify({'error': 'Invalid table_source'}), 400
        if email_delivery_mode not in {'attach_plus_summary'}:
            return jsonify({'error': 'Invalid email_delivery_mode'}), 400
        if email_recipient_mode not in {'custom_group_later', 'privilege_holders', 'custom_list'}:
            return jsonify({'error': 'Invalid email_recipient_mode'}), 400
        if email_recipient_mode == 'custom_list' and not email_recipients:
            return jsonify({'error': 'email_recipients required when recipient mode is custom_list'}), 400
        try:
            zig_exchange = float(zig_exchange_raw)
            if zig_exchange <= 0:
                raise ValueError("zig_exchange must be positive")
        except Exception:
            return jsonify({'error': 'Invalid zig_exchange. Expected a positive number.'}), 400

        try:
            hour_str, minute_str = schedule_time.split(':', 1)
            hour = int(hour_str)
            minute = int(minute_str)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time range")
        except Exception:
            return jsonify({'error': 'Invalid schedule_time. Expected HH:MM (24h).'}), 400

        try:
            dh_str, dm_str = fy_digest_time.split(':', 1)
            dh, dm = int(dh_str), int(dm_str)
            if dh < 0 or dh > 23 or dm < 0 or dm > 59:
                raise ValueError("Invalid digest time")
        except Exception:
            return jsonify({'error': 'Invalid fy_digest_time. Expected HH:MM (24h).'}), 400

        normalized_time = f"{hour:02d}:{minute:02d}"
        normalized_digest_time = f"{dh:02d}:{dm:02d}"
        AppSetting.set_value(
            'revenue_reports_source_mode',
            source_mode,
            current_user.id,
            'Source mode for daily revenue reports job'
        )
        AppSetting.set_value(
            'revenue_reports_schedule_time',
            normalized_time,
            current_user.id,
            'Daily run time (HH:MM, server local time) for revenue reports job'
        )
        AppSetting.set_value(
            'revenue_reports_table_source',
            table_source,
            current_user.id,
            'Data source for revenue report tables: latest_generated or template'
        )
        AppSetting.set_value(
            'revenue_reports_auto_email_enabled',
            str(auto_email_enabled).lower(),
            current_user.id,
            'Enable/disable auto email delivery for generated revenue reports'
        )
        AppSetting.set_value(
            'revenue_reports_email_delivery_mode',
            email_delivery_mode,
            current_user.id,
            'Email delivery mode for revenue reports'
        )
        AppSetting.set_value(
            'revenue_reports_email_recipient_mode',
            email_recipient_mode,
            current_user.id,
            'Email recipient strategy for revenue reports'
        )
        AppSetting.set_value(
            'revenue_reports_email_recipients',
            email_recipients,
            current_user.id,
            'Comma-separated recipient emails when mode is custom_list'
        )
        AppSetting.set_value(
            'revenue_reports_zig_exchange',
            str(zig_exchange),
            current_user.id,
            'ZIG exchange multiplier for Flash Smartlearning daily actual'
        )
        AppSetting.set_value(
            'akello_revenue_digest_enabled',
            str(fy_digest_enabled).lower(),
            current_user.id,
            'Enable monthly Akello Revenue FY digest email'
        )
        AppSetting.set_value(
            'akello_revenue_digest_schedule',
            normalized_digest_time,
            current_user.id,
            'Monthly FY digest run time (day 1, HH:MM server local)'
        )
        AppSetting.set_value(
            'akello_revenue_digest_period',
            fy_digest_period,
            current_user.id,
            'Default FY period code for digest email'
        )

        refresh_revenue_report_schedule(app)
        try:
            from app.scheduler import refresh_akello_revenue_digest_schedule
            refresh_akello_revenue_digest_schedule(app)
        except Exception:
            app.logger.exception("Failed to refresh FY digest schedule")

        return jsonify({
            'success': True,
            'message': 'Revenue report settings updated successfully',
            'settings': {
                'source_mode': source_mode,
                'schedule_time': normalized_time,
                'table_source': table_source,
                'auto_email_enabled': auto_email_enabled,
                'email_delivery_mode': email_delivery_mode,
                'email_recipient_mode': email_recipient_mode,
                'email_recipients': email_recipients,
                'zig_exchange': zig_exchange,
                'fy_digest_enabled': fy_digest_enabled,
                'fy_digest_time': normalized_digest_time,
                'fy_digest_period': fy_digest_period,
            }
        })
    except Exception as e:
        app.logger.error(f"Error updating revenue report settings: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/settings/revenue-reports', methods=['GET'])
@login_required
def get_revenue_report_settings():
    """Get revenue report source mode and schedule settings."""
    try:
        from app.models import AppSetting
        source_mode = AppSetting.get_value('revenue_reports_source_mode', 'db_template')
        schedule_time = AppSetting.get_value('revenue_reports_schedule_time', '06:00')
        table_source = AppSetting.get_value('revenue_reports_table_source', 'latest_generated')
        auto_email_enabled = AppSetting.get_value('revenue_reports_auto_email_enabled', 'false') == 'true'
        email_delivery_mode = AppSetting.get_value('revenue_reports_email_delivery_mode', 'attach_plus_summary')
        email_recipient_mode = AppSetting.get_value('revenue_reports_email_recipient_mode', 'custom_group_later')
        email_recipients = AppSetting.get_value('revenue_reports_email_recipients', '') or ''
        zig_exchange = float(AppSetting.get_value('revenue_reports_zig_exchange', '37') or 37)
        fy_digest_enabled = (AppSetting.get_value('akello_revenue_digest_enabled', 'false') or 'false').lower() == 'true'
        fy_digest_time = AppSetting.get_value('akello_revenue_digest_schedule', '07:00') or '07:00'
        fy_digest_period = AppSetting.get_value('akello_revenue_digest_period', 'FY2027') or 'FY2027'
        return jsonify({
            'success': True,
            'settings': {
                'source_mode': source_mode,
                'schedule_time': schedule_time,
                'table_source': table_source,
                'auto_email_enabled': auto_email_enabled,
                'email_delivery_mode': email_delivery_mode,
                'email_recipient_mode': email_recipient_mode,
                'email_recipients': email_recipients,
                'zig_exchange': zig_exchange,
                'fy_digest_enabled': fy_digest_enabled,
                'fy_digest_time': fy_digest_time,
                'fy_digest_period': fy_digest_period,
            }
        })
    except Exception as e:
        app.logger.error(f"Error getting revenue report settings: {e}")
        return jsonify({'error': str(e)}), 500
