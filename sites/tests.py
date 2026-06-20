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
