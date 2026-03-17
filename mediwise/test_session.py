from django.test import TestCase, Client
from django.urls import reverse
from main.models import Pharmacist, Order

class PharmacistOrderDetailsTest(TestCase):
    def setUp(self):
        # Create a test pharmacist
        self.pharmacist = Pharmacist.objects.create(
            first_name="Test",
            last_name="Pharmacist",
            email="test@pharmacy.com",
            password="test123",
            license_number="TEST123",
            phone_number="1234567890",
            address="Test Address"
        )
        
        # Create a test client and login
        self.client = Client()
        session = self.client.session
        session['pharmacist_id'] = self.pharmacist.id
        session.save()
        
        print(f"Session pharmacist_id: {session.get('pharmacist_id')}")
        
    def test_order_details_view(self):
        # Try to access the order details view
        response = self.client.get('/pharmacist/order/17/details/')
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.content}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success')}")
            if not data.get('success'):
                print(f"Error: {data.get('error')}")