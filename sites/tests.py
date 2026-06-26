import os
import tempfile
import shutil
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from sites.models import Site, SiteFile

User = get_user_model()

# Use a temporary directory for MEDIA_ROOT during testing
TEMP_MEDIA_ROOT = tempfile.mkdtemp()

@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class SiteFileDeleteTests(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(
            username='testuser',
            password='password123',
            email='test@example.com',
            role=User.Role.ENGINEER
        )
        
        # Create a site
        self.site = Site.objects.create(
            site_id='SITE_001',
            name='Site Teste 1',
            latitude=-23.550520,
            longitude=-46.633308,
            partner_company='Fornecedora Teste'
        )
        
        # Create a dummy file
        self.temp_file = SimpleUploadedFile(
            name="test_file.txt",
            content=b"test file content",
            content_type="text/plain"
        )
        
        # Create SiteFile
        self.site_file = SiteFile.objects.create(
            site=self.site,
            file=self.temp_file,
            description="Arquivo de teste",
            category=SiteFile.FileCategory.OTHER,
            uploaded_by=self.user
        )

    def tearDown(self):
        # Clean up temporary media files if they exist
        if os.path.exists(TEMP_MEDIA_ROOT):
            shutil.rmtree(TEMP_MEDIA_ROOT)

    def test_anonymous_user_cannot_delete_file(self):
        """Verify anonymous user is redirected to login when trying to delete a file."""
        url = reverse('delete_file', kwargs={'file_id': self.site_file.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        # Verify file still exists in database
        self.assertTrue(SiteFile.objects.filter(id=self.site_file.id).exists())

    def test_authenticated_user_can_delete_file_physically_and_from_db(self):
        """Verify authenticated user can delete a file, removing it physically and from database."""
        # Log in the user
        self.client.login(username='testuser', password='password123')
        
        # Get physical path of file before deletion
        file_path = self.site_file.file.path
        self.assertTrue(os.path.exists(file_path), "File should exist physically before delete")
        
        # Call delete view
        url = reverse('delete_file', kwargs={'file_id': self.site_file.id})
        response = self.client.get(url)  # Since the button uses a regular <a> link, it does a GET request.
        
        # Verify redirect manually to avoid rendering and django test copy(context) bug in Python 3.14
        self.assertEqual(response.status_code, 302)
        expected_url = reverse('site_detail', kwargs={'pk': self.site.pk})
        self.assertTrue(response.url.endswith(expected_url), f"Expected URL to end with {expected_url}, got {response.url}")
        
        # Verify file is deleted from database
        self.assertFalse(SiteFile.objects.filter(id=self.site_file.id).exists())
        
        # Verify file is deleted physically from disk
        self.assertFalse(os.path.exists(file_path), "File should be removed physically from disk")


class SiteGeocodingAndOptionalCoordsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='engineer',
            password='password123',
            email='engineer@example.com',
            role=User.Role.ENGINEER
        )

    def test_create_site_with_optional_coordinates(self):
        """Test that we can create a Site with null coordinates and optional address."""
        site = Site.objects.create(
            site_id='SITE_NULL_COORDS',
            name='Site Sem Coordenadas',
            address='Av. Paulista, 1000, SP',
            latitude=None,
            longitude=None
        )
        self.assertEqual(site.address, 'Av. Paulista, 1000, SP')
        self.assertNil = self.assertIsNone(site.latitude)
        self.assertIsNone(site.longitude)

    def test_site_list_post_creates_site_with_address_and_optional_coordinates(self):
        """Test that the site creation view processes address and handles empty coordinates correctly."""
        self.client.login(username='engineer', password='password123')
        url = reverse('site_list')
        
        # Scenario 1: address only, empty coordinates
        post_data = {
            'site_id': 'SITE_ADDR_ONLY',
            'name': 'Site com Endereço Apenas',
            'address': 'Rua Augusta, 1500, São Paulo',
            'latitude': '',
            'longitude': '',
            'scope_type': 'LAUDOS'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        
        site = Site.objects.get(site_id='SITE_ADDR_ONLY')
        self.assertEqual(site.address, 'Rua Augusta, 1500, São Paulo')
        self.assertIsNone(site.latitude)
        self.assertIsNone(site.longitude)

    def test_site_detail_post_updates_address_and_coordinates(self):
        """Test that updating workflow details successfully saves address and coordinates."""
        site = Site.objects.create(
            site_id='SITE_EDIT_GEOLOC',
            name='Site Edicao Geoloc',
            latitude=None,
            longitude=None
        )
        self.client.login(username='engineer', password='password123')
        url = reverse('site_detail', kwargs={'pk': site.pk})
        
        post_data = {
            'action': 'update_location',
            'address': 'Av. Brigadeiro Faria Lima, 2000',
            'latitude': '-23.568910',
            'longitude': '-46.685240'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        
        site.refresh_from_db()
        self.assertEqual(site.address, 'Av. Brigadeiro Faria Lima, 2000')
        self.assertEqual(float(site.latitude), -23.568910)
        self.assertEqual(float(site.longitude), -46.685240)

    def test_site_detail_post_updates_all_fields(self):
        """Test that updating site details successfully saves ID, Name, Scope, Partner, and Access Status."""
        site = Site.objects.create(
            site_id='SITE_EDIT_ALL_OLD',
            name='Site Antigo Nome',
            scope_type='LAUDOS',
            partner_company='Parceiro Antigo',
            access_status='NOT_STARTED'
        )
        self.client.login(username='engineer', password='password123')
        url = reverse('site_detail', kwargs={'pk': site.pk})
        
        post_data = {
            'action': 'update_location',
            'site_id': 'SITE_EDIT_ALL_NEW',
            'name': 'Site Novo Nome',
            'scope_type': 'INSTALACAO',
            'partner_company': 'Parceiro Novo',
            'access_status': 'RELEASED',
            'description': 'Nova descricao editada'
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        
        site.refresh_from_db()
        self.assertEqual(site.site_id, 'SITE_EDIT_ALL_NEW')
        self.assertEqual(site.name, 'Site Novo Nome')
        self.assertEqual(site.scope_type, 'INSTALACAO')
        self.assertEqual(site.partner_company, 'Parceiro Novo')
        self.assertEqual(site.access_status, 'RELEASED')
        self.assertEqual(site.description, 'Nova descricao editada')

    def test_site_without_planned_dates_gets_maintenance_status(self):
        """Test that a Site created without planned dates gets the MAINTENANCE status automatically."""
        site = Site.objects.create(
            site_id='SITE_NO_PLAN_DATES',
            name='Site Sem Planejamento',
            planned_survey_date=None,
            planned_report_date=None
        )
        self.assertEqual(site.status, Site.SiteStatus.MAINTENANCE)

    def test_partner_analytics_lead_times(self):
        """Test that partner lead times are correctly calculated in the dashboard view."""
        from django.utils import timezone
        import datetime
        from unittest.mock import patch
        
        # Log in
        self.client.login(username='engineer', password='password123')
        
        # Create a site with actual dates
        site = Site.objects.create(
            site_id='SITE_ANALYTICS_TEST',
            name='Site Analytics',
            partner_company='BTL_TEST',
            actual_survey_date=timezone.localdate() - datetime.timedelta(days=6), # Completed survey 6 days ago
            actual_report_date=timezone.localdate() - datetime.timedelta(days=2), # Completed report 2 days ago
        )
        
        # Manually update created_at to 10 days ago (since auto_now_add makes it read-only on save)
        Site.objects.filter(pk=site.pk).update(created_at=timezone.now() - datetime.timedelta(days=10))
        
        url = reverse('site_list')
        
        # Patch the copy function to bypass Django's Python 3.14 context copy bug
        with patch('django.test.client.copy', lambda x: x):
            response = self.client.get(url)
            
        self.assertEqual(response.status_code, 200)
        
        # Check context calculations
        partner_stats = response.context['partner_stats']
        # We expect BTL_TEST to be in partner_stats with average times:
        # survey_days: created 10 days ago -> survey 6 days ago = 4 days
        # report_days: survey 6 days ago -> report 2 days ago = 4 days
        # total_days: 10 days ago -> 2 days ago = 8 days
        btl_stat = next((item for item in partner_stats if item['partner'] == 'BTL_TEST'), None)
        self.assertIsNotNone(btl_stat)
        self.assertEqual(btl_stat['total_sites'], 1)
        self.assertEqual(btl_stat['avg_survey_days'], 4.0)
        self.assertEqual(btl_stat['avg_report_days'], 4.0)
        self.assertEqual(btl_stat['avg_total_days'], 8.0)


class SiteRolloutWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='engineer_workflow',
            password='password123',
            email='engineer_workflow@example.com',
            role=User.Role.ENGINEER
        )

    def test_default_access_status_based_on_site_type(self):
        """Test that default access_status matches site_type on creation."""
        # All structure types require access release, so they should start as NOT_STARTED by default
        for st in [Site.SiteType.ROOFTOP, Site.SiteType.GREENFIELD, Site.SiteType.INDOOR, Site.SiteType.STREET]:
            site = Site.objects.create(
                site_id=f'SITE_WF_{st}',
                name=f'Site {st}',
                site_type=st
            )
            self.assertEqual(site.access_status, Site.AccessStatus.NOT_STARTED)

    def test_access_workflow_transitions(self):
        """Test transitioning access_status through update_access view actions."""
        self.client.login(username='engineer_workflow', password='password123')
        site = Site.objects.create(
            site_id='SITE_TRANSITIONS',
            name='Site Transicoes',
            site_type=Site.SiteType.ROOFTOP
        )
        self.assertEqual(site.access_status, Site.AccessStatus.NOT_STARTED)

        # Step 2a: Request access
        url = reverse('site_detail', kwargs={'pk': site.pk})
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'request_access'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.REQUESTED)
        self.assertIsNotNone(site.access_requested_date)
        self.assertIsNone(site.access_released_date)

        # Step 2b: Release access
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'release_access'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.RELEASED)
        self.assertIsNotNone(site.access_released_date)

        # Step 2c: Skip access
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'skip_access'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.NOT_REQUIRED)
        self.assertIsNone(site.access_requested_date)
        self.assertIsNone(site.access_released_date)

        # Step 2d: Reset access
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'reset_access'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.NOT_STARTED)
        self.assertIsNone(site.access_requested_date)
        self.assertIsNone(site.access_released_date)

    def test_is_survey_due_property(self):
        """Test is_survey_due property behavior under different date configurations."""
        from django.utils import timezone
        import datetime
        
        today = timezone.localdate()
        site = Site.objects.create(
            site_id='SITE_DUE_PROP',
            name='Site Due Property'
        )
        
        # 1. No planned survey date -> is_survey_due should be False
        self.assertFalse(site.is_survey_due)

        # 2. Planned survey date in the future -> is_survey_due should be False
        site.planned_survey_date = today + datetime.timedelta(days=1)
        site.save()
        self.assertFalse(site.is_survey_due)

        # 3. Planned survey date today -> is_survey_due should be True
        site.planned_survey_date = today
        site.save()
        self.assertTrue(site.is_survey_due)

        # 4. Planned survey date in the past -> is_survey_due should be True
        site.planned_survey_date = today - datetime.timedelta(days=2)
        site.save()
        self.assertTrue(site.is_survey_due)

        # 5. Survey already realized -> is_survey_due should be False
        site.actual_survey_date = today
        site.save()
        self.assertFalse(site.is_survey_due)

    def test_is_report_due_property(self):
        """Test is_report_due property behavior under different date configurations."""
        from django.utils import timezone
        import datetime
        
        today = timezone.localdate()
        site = Site.objects.create(
            site_id='SITE_REP_DUE_P',
            name='Site Report Due Property'
        )
        
        # 1. No planned report date -> is_report_due should be False
        self.assertFalse(site.is_report_due)

        # 2. Planned report date in the future -> is_report_due should be False
        site.planned_report_date = today + datetime.timedelta(days=1)
        site.save()
        self.assertFalse(site.is_report_due)

        # 3. Planned report date today -> is_report_due should be True
        site.planned_report_date = today
        site.save()
        self.assertTrue(site.is_report_due)

        # 4. Planned report date in the past -> is_report_due should be True
        site.planned_report_date = today - datetime.timedelta(days=2)
        site.save()
        self.assertTrue(site.is_report_due)

        # 5. Report already realized -> is_report_due should be False
        site.actual_report_date = today
        site.save()
        self.assertFalse(site.is_report_due)

    def test_reschedule_increments_counter(self):
        """Test that modifying planned dates increments the reschedule_count."""
        self.client.login(username='engineer_workflow', password='password123')
        from django.utils import timezone
        import datetime
        
        today = timezone.localdate()
        site = Site.objects.create(
            site_id='SITE_RESCHED_COUNT',
            name='Site Replanejamento',
            planned_survey_date=today,
            planned_report_date=today + datetime.timedelta(days=5)
        )
        self.assertEqual(site.reschedule_count, 0)

        # Post update with new dates to trigger reschedule
        url = reverse('site_detail', kwargs={'pk': site.pk})
        response = self.client.post(url, {
            'action': 'update_workflow',
            'scope_type': 'LAUDOS',
            'planned_survey_date': (today + datetime.timedelta(days=2)).strftime('%Y-%m-%d'),
            'planned_report_date': (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.reschedule_count, 1)

    def test_reschedule_creates_history(self):
        """Test that rescheduling creates a SiteRescheduleHistory log record."""
        self.client.login(username='engineer_workflow', password='password123')
        from django.utils import timezone
        import datetime
        from .models import SiteRescheduleHistory
        
        today = timezone.localdate()
        site = Site.objects.create(
            site_id='SITE_RESCHED_HIST',
            name='Site Histórico Replanejamento',
            planned_survey_date=today,
            planned_report_date=today + datetime.timedelta(days=5)
        )
        self.assertEqual(site.reschedule_histories.count(), 0)

        # Post update with new dates and reason to trigger reschedule
        url = reverse('site_detail', kwargs={'pk': site.pk})
        response = self.client.post(url, {
            'action': 'update_workflow',
            'scope_type': 'LAUDOS',
            'planned_survey_date': (today + datetime.timedelta(days=2)).strftime('%Y-%m-%d'),
            'planned_report_date': (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d'),
            'reschedule_reason': 'Chuva forte'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.reschedule_count, 1)
        self.assertEqual(site.reschedule_histories.count(), 1)
        
        history = site.reschedule_histories.first()
        self.assertEqual(history.previous_planned_survey_date, today)
        self.assertEqual(history.new_planned_survey_date, today + datetime.timedelta(days=2))
        self.assertEqual(history.reason, 'Chuva forte')
        self.assertEqual(history.created_by.username, 'engineer_workflow')

    def test_report_reschedule_flow(self):
        """Test that rescheduling the report (Stage 4) creates history, increments counter, and keeps survey date."""
        self.client.login(username='engineer_workflow', password='password123')
        from django.utils import timezone
        import datetime
        from .models import SiteRescheduleHistory
        
        today = timezone.localdate()
        site = Site.objects.create(
            site_id='SITE_REP_RESCH',
            name='Site Report Reschedule',
            planned_survey_date=today - datetime.timedelta(days=5),
            planned_report_date=today
        )
        self.assertEqual(site.reschedule_histories.count(), 0)

        # Post update with new report date, same survey date, and reason
        url = reverse('site_detail', kwargs={'pk': site.pk})
        response = self.client.post(url, {
            'action': 'update_workflow',
            'scope_type': 'LAUDOS',
            'planned_survey_date': (today - datetime.timedelta(days=5)).strftime('%Y-%m-%d'),
            'planned_report_date': (today + datetime.timedelta(days=3)).strftime('%Y-%m-%d'),
            'reschedule_reason': 'Atraso na vistoria tecnica'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.reschedule_count, 1)
        self.assertEqual(site.reschedule_histories.count(), 1)
        
        history = site.reschedule_histories.first()
        self.assertEqual(history.previous_planned_report_date, today)
        self.assertEqual(history.new_planned_report_date, today + datetime.timedelta(days=3))
        # Survey date should remain unchanged in history
        self.assertEqual(history.previous_planned_survey_date, today - datetime.timedelta(days=5))
        self.assertEqual(history.new_planned_survey_date, today - datetime.timedelta(days=5))
        self.assertEqual(history.reason, 'Atraso na vistoria tecnica')

    def test_delete_site_permitted(self):
        """Test that Admin or Engineer can delete a site."""
        self.client.login(username='engineer_workflow', password='password123')
        site = Site.objects.create(
            site_id='SITE_DELETE_OK',
            name='Site to Delete'
        )
        url = reverse('delete_site', kwargs={'pk': site.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Site.objects.filter(site_id='SITE_DELETE_OK').exists())

    def test_delete_site_restricted_for_technician(self):
        """Test that Technician is not allowed to delete a site."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        tech_user = User.objects.create_user(
            username='tech_delete',
            password='password123',
            email='tech_delete@example.com',
            role=User.Role.TECHNICIAN
        )
        self.client.login(username='tech_delete', password='password123')
        site = Site.objects.create(
            site_id='SITE_DELETE_FAIL',
            name='Site Safe'
        )
        url = reverse('delete_site', kwargs={'pk': site.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Site.objects.filter(SITE_DELETE_FAIL=site.site_id).exists() if hasattr(self, 'dummy') else Site.objects.filter(site_id='SITE_DELETE_FAIL').exists())

    def test_dynamic_update_stage_actions(self):
        """Test that generic stages can be updated, skipped, and reset, and their statuses are saved in JSON."""
        self.client.login(username='engineer_workflow', password='password123')
        site = Site.objects.create(
            site_id='SITE_DYN_STAGES',
            name='Site Estágios Dinâmicos',
            scope_type=Site.ScopeType.LAUDOS
        )
        
        url = reverse('site_detail', kwargs={'pk': site.pk})
        
        # 1. Complete a generic stage e.g. "Acionamento Parceiro"
        response = self.client.post(url, {
            'action': 'update_stage',
            'stage_name': 'Acionamento Parceiro',
            'stage_status': 'DONE',
            'stage_date': '2026-06-23',
            'partner_company': 'Parceiro BTL'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.stages_status['Acionamento Parceiro']['status'], 'DONE')
        self.assertEqual(site.stages_status['Acionamento Parceiro']['date'], '2026-06-23')
        self.assertEqual(site.partner_company, 'Parceiro BTL')

        # 2. Skip a generic stage e.g. "Acionamento Parceiro"
        response = self.client.post(url, {
            'action': 'update_stage',
            'stage_name': 'Acionamento Parceiro',
            'stage_status': 'SKIPPED'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.stages_status['Acionamento Parceiro']['status'], 'SKIPPED')

        # 3. Reset a generic stage back to PENDING
        response = self.client.post(url, {
            'action': 'update_stage',
            'stage_name': 'Acionamento Parceiro',
            'stage_status': 'PENDING'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.stages_status['Acionamento Parceiro']['status'], 'PENDING')
        self.assertIsNone(site.stages_status['Acionamento Parceiro']['date'])

    def test_optional_site_id(self):
        """Test that leaving site_id blank allows registering the site with null ID, and multiple blank IDs are allowed."""
        self.client.login(username='engineer_workflow', password='password123')
        
        # Register first site without ID
        url = reverse('site_list')
        response1 = self.client.post(url, {
            'site_id': '',
            'name': 'RJPLB Site One',
            'scope_type': 'LAUDOS'
        })
        self.assertEqual(response1.status_code, 302)
        site1 = Site.objects.filter(name='RJPLB Site One').first()
        self.assertIsNotNone(site1)
        self.assertIsNone(site1.site_id)

        # Register second site without ID (should succeed since unique constraint allows multiple NULL values)
        response2 = self.client.post(url, {
            'site_id': '',
            'name': 'RJPLB Site Two',
            'scope_type': 'LAUDOS'
        })
        self.assertEqual(response2.status_code, 302)
        site2 = Site.objects.filter(name='RJPLB Site Two').first()
        self.assertIsNotNone(site2)
        self.assertIsNone(site2.site_id)


class SiteOperatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='engineer_operator',
            password='password123',
            email='eng_op@example.com',
            role=User.Role.ENGINEER
        )

    def test_create_site_with_operator(self):
        """Test that we can create a Site with a specific operator choice."""
        self.client.login(username='engineer_operator', password='password123')
        url = reverse('site_list')
        response = self.client.post(url, {
            'site_id': 'SITE_OP_01',
            'name': 'Site Tim Test',
            'scope_type': 'LAUDOS',
            'operator': 'TIM'
        })
        self.assertEqual(response.status_code, 302)
        site = Site.objects.get(site_id='SITE_OP_01')
        self.assertEqual(site.operator, 'TIM')
        self.assertEqual(site.get_operator_display(), 'Tim')

    def test_edit_site_operator(self):
        """Test that we can edit a Site's operator choice via site_detail view."""
        site = Site.objects.create(
            site_id='SITE_OP_02',
            name='Site Claro Test',
            scope_type=Site.ScopeType.LAUDOS,
            operator='CLARO'
        )
        self.client.login(username='engineer_operator', password='password123')
        url = reverse('site_detail', kwargs={'pk': site.pk})
        response = self.client.post(url, {
            'action': 'update_location',
            'site_id': 'SITE_OP_02',
            'name': 'Site Claro Test Edit',
            'operator': 'VIVO'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.operator, 'VIVO')
        self.assertEqual(site.name, 'Site Claro Test Edit')

    def test_delete_site_with_null_site_id(self):
        """Test that a site with null site_id can be deleted without causing a TypeError/500 error."""
        site = Site.objects.create(
            site_id=None,
            name='Site Null ID Test',
            scope_type=Site.ScopeType.LAUDOS
        )
        self.client.login(username='engineer_operator', password='password123')
        url = reverse('delete_site', kwargs={'pk': site.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Site.objects.filter(pk=site.pk).exists())

    def test_custom_access_dates(self):
        """Test that update_access action accepts and parses custom request/release dates."""
        site = Site.objects.create(
            site_id='SITE_ACCESS_DATE_TEST',
            name='Access Date Site',
            scope_type=Site.ScopeType.LAUDOS,
            access_status=Site.AccessStatus.NOT_STARTED
        )
        self.client.login(username='engineer_operator', password='password123')
        url = reverse('site_detail', kwargs={'pk': site.pk})
        
        # Test rendering of the page
        render_response = self.client.get(url)
        self.assertEqual(render_response.status_code, 200)
        
        # 1. Request access with a custom past date
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'request_access',
            'access_requested_date': '2026-05-10'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.REQUESTED)
        self.assertEqual(site.access_requested_date.isoformat(), '2026-05-10')

        # 2. Release access with a custom past date
        response = self.client.post(url, {
            'action': 'update_access',
            'access_action': 'release_access',
            'access_released_date': '2026-05-15'
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.access_status, Site.AccessStatus.RELEASED)
        self.assertEqual(site.access_released_date.isoformat(), '2026-05-15')
        self.assertEqual(site.access_lead_time, 5)


class CalendarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calendar_user',
            password='password123',
            email='calendar@example.com',
            role=User.Role.ENGINEER
        )
        self.client.login(username='calendar_user', password='password123')

    def test_holiday_calculation(self):
        """Test that get_br_rj_holidays returns correct holidays for year 2026."""
        from .holidays import get_br_rj_holidays
        import datetime
        
        holidays = get_br_rj_holidays(2026)
        
        # Fixed national
        self.assertIn(datetime.date(2026, 1, 1), holidays)
        self.assertEqual(holidays[datetime.date(2026, 1, 1)], "Confraternização Universal")
        
        # Fixed local
        self.assertIn(datetime.date(2026, 4, 23), holidays)
        self.assertEqual(holidays[datetime.date(2026, 4, 23)], "Dia de São Jorge")
        
        # Easter 2026 is April 5. Sexta-feira santa is April 3.
        self.assertIn(datetime.date(2026, 4, 3), holidays)
        self.assertEqual(holidays[datetime.date(2026, 4, 3)], "Sexta-feira Santa")

    def test_calendar_events_api(self):
        """Test calendar_events_api returns correct JSON response with notes, holidays and planned dates."""
        import datetime
        from .models import CalendarNote, Site
        
        # Create a Note
        note = CalendarNote.objects.create(
            date=datetime.date(2026, 6, 15),
            title="Note Test",
            description="Testing note"
        )
        
        # Create a Site with planned dates
        site = Site.objects.create(
            site_id="SITE_CAL_1",
            name="Calendar Site",
            planned_survey_date=datetime.date(2026, 6, 20),
            planned_report_date=datetime.date(2026, 6, 25),
            scope_type=Site.ScopeType.LAUDOS
        )
        
        url = reverse('calendar_events_api')
        response = self.client.get(url, {'start': '2026-06-01', 'end': '2026-06-30'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Verify note is present
        note_event = next((item for item in data if item['id'] == f"note_{note.id}"), None)
        self.assertIsNotNone(note_event)
        self.assertEqual(note_event['title'], "Note Test")
        self.assertEqual(note_event['date'], "2026-06-15")
        
        # Verify site planned survey is present
        survey_event = next((item for item in data if item['id'] == f"site_survey_{site.id}"), None)
        self.assertIsNotNone(survey_event)
        self.assertEqual(survey_event['title'], "Vistoria: SITE_CAL_1")
        self.assertEqual(survey_event['date'], "2026-06-20")
        
        # Verify site planned report is present
        report_event = next((item for item in data if item['id'] == f"site_report_{site.id}"), None)
        self.assertIsNotNone(report_event)
        self.assertEqual(report_event['title'], "Laudo: SITE_CAL_1")
        self.assertEqual(report_event['date'], "2026-06-25")

    def test_calendar_note_crud_actions(self):
        """Test adding, editing, and deleting a CalendarNote via AJAX views."""
        from .models import CalendarNote
        
        # 1. Add Note
        url_add = reverse('add_calendar_note')
        response = self.client.post(url_add, {
            'date': '2026-06-10',
            'title': 'New Note',
            'description': 'Description content'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        note = CalendarNote.objects.get(title='New Note')
        self.assertEqual(note.description, 'Description content')
        self.assertEqual(note.date.isoformat(), '2026-06-10')
        
        # 2. Edit Note
        url_edit = reverse('edit_calendar_note')
        response = self.client.post(url_edit, {
            'id': note.id,
            'title': 'New Note Edited',
            'description': 'Description content edited'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        note.refresh_from_db()
        self.assertEqual(note.title, 'New Note Edited')
        self.assertEqual(note.description, 'Description content edited')
        
        # 3. Delete Note
        url_delete = reverse('delete_calendar_note')
        response = self.client.post(url_delete, {
            'id': note.id
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertFalse(CalendarNote.objects.filter(id=note.id).exists())





