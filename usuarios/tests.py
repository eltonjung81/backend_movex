from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Usuario, Motorista, Passageiro

class UsuarioTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.registro_motorista_url = reverse('registro-motorista')
        self.registro_passageiro_url = reverse('registro-passageiro')
        self.login_url = reverse('login')
        
        # Dados de teste
        self.dados_motorista = {
            "usuario": {
                "cpf": "12345678900",
                "nome": "Teste",
                "sobrenome": "Motorista",
                "password": "senha123",
                "password2": "senha123",
                "telefone": "51999999999",
                "email": "motorista@teste.com"
            },
            "cnh": "1234567890",
            "categoria_cnh": "B",
            "placa_veiculo": "ABC1234",
            "modelo_veiculo": "Modelo Test",
            "cor_veiculo": "Preto"
        }
        
        self.dados_passageiro = {
            "cpf": "98765432100",
            "nome": "Teste",
            "sobrenome": "Passageiro",
            "password": "senha123",
            "password2": "senha123",
            "telefone": "51988888888",
            "email": "passageiro@teste.com"
        }
    
    def test_registro_motorista(self):
        """Teste de registro de motorista"""
        response = self.client.post(
            self.registro_motorista_url, 
            self.dados_motorista, 
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Motorista.objects.count(), 1)
    
    def test_registro_passageiro(self):
        """Teste de registro de passageiro"""
        response = self.client.post(
            self.registro_passageiro_url, 
            self.dados_passageiro, 
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Passageiro.objects.count(), 1)
    
    def test_login_motorista(self):
        """Teste de login de motorista"""
        # Primeiro registrar um motorista
        self.client.post(
            self.registro_motorista_url, 
            self.dados_motorista, 
            format='json'
        )
        
        # Tentar fazer login
        response = self.client.post(
            self.login_url,
            {
                "cpf": "12345678900",
                "password": "senha123"
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
