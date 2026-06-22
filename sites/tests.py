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
            'scope_type': 'LAUDO'
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
        # Rooftop requires access release (so status starts as NOT_STARTED)
        site1 = Site.objects.create(
            site_id='SITE_WF_ROOFTOP',
            name='Site Rooftop',
            site_type=Site.SiteType.ROOFTOP
        )
        self.assertEqual(site1.access_status, Site.AccessStatus.NOT_STARTED)

        # NENHUM does not require access release (so status starts as NOT_REQUIRED)
        site2 = Site.objects.create(
            site_id='SITE_WF_NONE',
            name='Site Sem Acesso',
            site_type=Site.SiteType.NENHUM
        )
        self.assertEqual(site2.access_status, Site.AccessStatus.NOT_REQUIRED)

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
            'scope_type': 'LAUDO',
            'planned_survey_date': (today + datetime.timedelta(days=2)).strftime('%Y-%m-%d'),
            'planned_report_date': (today + datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        })
        self.assertEqual(response.status_code, 302)
        site.refresh_from_db()
        self.assertEqual(site.reschedule_count, 1)

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
        self.assertTrue(Site.objects.filter(site_id='SITE_DELETE_FAIL').exists())



