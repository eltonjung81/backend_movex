from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token  # Garantindo que o Token seja importado corretamente
from django.contrib.auth import authenticate
from .serializers import MotoristaSerializer, LoginSerializer, RegistroPassageiroSerializer, LoginPassageiroSerializer
from .models import Usuario, Motorista
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
import logging
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

# Create your views here.

class RegistroMotoristaView(APIView):
    """
    View para registro de novos motoristas
    """
    permission_classes = []  # Remove a proteção de autenticação para esta view
    def post(self, request):
        print(f"[DEBUG] Registro motorista - dados recebidos: {request.data}")  # Log para debug
        serializer = MotoristaSerializer(data=request.data)
        if serializer.is_valid():
            motorista = serializer.save()
            print(f"[DEBUG] Motorista criado com sucesso: {motorista}")  # Log para debug
            return Response(
                {"message": "Motorista cadastrado com sucesso!"},
                status=status.HTTP_201_CREATED
            )
        print(f"[DEBUG] Erros de validação: {serializer.errors}")  # Log para debug
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    """
    View para autenticação de usuários (motoristas e passageiros)
    """
    permission_classes = []  # Remove a proteção de autenticação para esta view
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            cpf = serializer.validated_data['cpf']
            password = serializer.validated_data['password']
            user = authenticate(request, username=cpf, password=password)
            
            if user is not None:
                # Verifica se o usuário é motorista quando não estiver usando a rota específica
                if not request.path.endswith('login/motorista/') and user.tipo_usuario == 'MOTORISTA':
                    # Cria ou obtém um token para o usuário
                    token, created = Token.objects.get_or_create(user=user)
                    
                    # Prepara os dados de resposta
                    response_data = {
                        'success': True,
                        'token': token.key,
                        'user_id': user.id,
                        'cpf': user.cpf,
                        'nome': user.nome,
                        'sobrenome': user.sobrenome,
                        'tipo_usuario': user.tipo_usuario
                    }
                    
                    # Adiciona dados específicos do motorista se o usuário for um motorista
                    try:
                        motorista = Motorista.objects.get(cpf=user.cpf)
                        response_data['motorista'] = {
                            'id': user.cpf,  # Usando CPF como ID do motorista
                            'cnh': motorista.cnh,
                            'placa_veiculo': motorista.placa_veiculo,
                            'modelo_veiculo': motorista.modelo_veiculo,
                            'cor_veiculo': motorista.cor_veiculo,
                            'telefone': user.telefone,
                            'avaliacao_media': float(motorista.avaliacao_media),
                            'nome_completo': user.get_full_name()
                        }
                    except Exception as e:
                        print(f"Erro ao obter dados do motorista: {str(e)}")
                        pass
                    
                    return Response(response_data)
                
                # Verifica se a rota de login é para motorista e se o usuário não é motorista
                if request.path.endswith('login/motorista/') and user.tipo_usuario != 'MOTORISTA':
                    return Response(
                        {"error": "Acesso não autorizado. Essa conta não é de motorista."},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                # Cria ou obtém um token para o usuário
                token, created = Token.objects.get_or_create(user=user)
                
                # Prepara os dados de resposta
                response_data = {
                    'success': True,
                    'token': token.key,
                    'user_id': user.id,
                    'cpf': user.cpf,
                    'nome': user.nome,
                    'sobrenome': user.sobrenome,
                    'tipo_usuario': user.tipo_usuario
                }
                
                # Adiciona dados específicos do motorista se o usuário for um motorista
                if user.tipo_usuario == 'MOTORISTA':
                    try:
                        motorista = Motorista.objects.get(cpf=user.cpf)
                        response_data['motorista'] = {
                            'id': user.cpf,  # Usando CPF como ID do motorista
                            'cnh': motorista.cnh,
                            'placa_veiculo': motorista.placa_veiculo,
                            'modelo_veiculo': motorista.modelo_veiculo,
                            'cor_veiculo': motorista.cor_veiculo,
                            'telefone': user.telefone,
                            'avaliacao_media': float(motorista.avaliacao_media),
                            'nome_completo': user.get_full_name()
                        }
                    except Exception as e:
                        print(f"Erro ao obter dados do motorista: {str(e)}")
                        pass
                
                return Response(response_data)
            else:
                return Response(
                    {"error": "Credenciais inválidas"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class BuscarDadosMotoristaView(APIView):
    """
    View para buscar dados do motorista pelo CPF
    """
    permission_classes = [AllowAny]  # Permitir acesso sem autenticação
    
    def post(self, request):
        logger.debug(f"Método da requisição: {request.method}")
        logger.debug(f"Dados recebidos: {request.data}")
        
        cpf = request.data.get('cpf')
        logger.debug(f"CPF extraído: {cpf}")
        
        if not cpf:
            logger.error("CPF não fornecido na requisição")
            return Response(
                {"success": False, "error": "CPF não fornecido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            usuario = Usuario.objects.get(cpf=cpf, tipo_usuario='MOTORISTA')
            motorista = usuario.motorista
            
            # Preparar os dados de resposta
            response_data = {
                'success': True,
                'data': {
                    'id': cpf,
                    'nome': usuario.get_full_name(),
                    'modeloCarro': motorista.modelo_veiculo,
                    'corCarro': motorista.cor_veiculo,
                    'placaCarro': motorista.placa_veiculo,
                    'telefone': usuario.telefone
                }
            }
            
            logger.debug(f"Resposta preparada: {response_data}")
            return Response(response_data)
        except (Usuario.DoesNotExist, Motorista.DoesNotExist) as e:
            logger.error(f"Motorista não encontrado para CPF {cpf}: {str(e)}")
            return Response(
                {"success": False, "error": "Motorista não encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erro ao buscar dados do motorista: {str(e)}")
            return Response(
                {"success": False, "error": f"Erro ao buscar dados do motorista: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RegistroPassageiroView(APIView):
    """
    View para registro de novos passageiros
    """
    permission_classes = []  # Remove a proteção de autenticação para esta view
    
    def post(self, request):
        print(f"[DEBUG] Dados recebidos: {request.data}")  # Log para debug
        serializer = RegistroPassageiroSerializer(data=request.data)
        if serializer.is_valid():
            try:
                usuario = serializer.save()
                print(f"[DEBUG] Usuário criado com sucesso: {usuario}")  # Log para debug
                return Response(
                    {"message": "Passageiro cadastrado com sucesso!"},
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                print(f"[DEBUG] Erro ao salvar usuário: {str(e)}")  # Log para debug
                return Response(
                    {"error": f"Erro ao criar usuário: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        print(f"[DEBUG] Erros de validação: {serializer.errors}")  # Log para debug
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginPassageiroView(APIView):
    """
    View para autenticação de passageiros
    """
    permission_classes = []  # Remove a proteção de autenticação para esta view
    
    def post(self, request):
        # Log para debug
        print(f"[DEBUG] Login passageiro - dados recebidos: {request.data}")
        
        serializer = LoginPassageiroSerializer(data=request.data)
        if serializer.is_valid():
            cpf = serializer.validated_data['cpf']
            password = serializer.validated_data['password']
            
            try:
                # Tenta encontrar o usuário pelo CPF primeiro
                usuario = Usuario.objects.get(cpf=cpf, tipo_usuario='PASSAGEIRO')
                # Tenta autenticar com as credenciais fornecidas
                user = authenticate(request, username=cpf, password=password)
                
                if user is not None and user.tipo_usuario == 'PASSAGEIRO':
                    # Aqui estava o erro - certifique-se de que Token está importado corretamente
                    token, created = Token.objects.get_or_create(user=user)
                    return Response({
                        'success': True,
                        'token': token.key,
                        'user_id': user.id,
                        'cpf': user.cpf,
                        'nome': user.nome,
                        'sobrenome': user.sobrenome,
                        'telefone': user.telefone,
                        'email': user.email,
                    })
                else:
                    print(f"[DEBUG] Login passageiro - falha na autenticação para CPF: {cpf}")
                    return Response(
                        {"error": "Credenciais inválidas ou usuário não é passageiro"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            except Usuario.DoesNotExist:
                print(f"[DEBUG] Login passageiro - usuário não encontrado para CPF: {cpf}")
                return Response(
                    {"error": "Usuário não encontrado"},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            print(f"[DEBUG] Login passageiro - erros de validação: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class LoginMotoristaView(APIView):
    """
    View para autenticação exclusiva de motoristas
    """
    permission_classes = []  # No auth required for login
    
    def post(self, request):
        print(f"[DEBUG] Login motorista - dados recebidos: {request.data}")
        
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            cpf = serializer.validated_data['cpf']
            password = serializer.validated_data['password']
            
            try:
                # Verifica primeiro se o usuário existe e é motorista
                usuario = Usuario.objects.get(cpf=cpf, tipo_usuario='MOTORISTA')
                user = authenticate(request, username=cpf, password=password)
                
                if user is not None and user.tipo_usuario == 'MOTORISTA':
                    # Cria ou obtém um token para o usuário
                    token, created = Token.objects.get_or_create(user=user)
                    
                    # Prepara os dados de resposta
                    response_data = {
                        'success': True,
                        'token': token.key,
                        'user_id': user.id,
                        'cpf': user.cpf,
                        'nome': user.nome,
                        'sobrenome': user.sobrenome,
                        'tipo_usuario': user.tipo_usuario
                    }
                    
                    # Adiciona dados específicos do motorista
                    try:
                        motorista = Motorista.objects.get(cpf=user.cpf)
                        response_data['motorista'] = {
                            'id': user.cpf,  # Usando CPF como ID do motorista
                            'cnh': motorista.cnh,
                            'placa_veiculo': motorista.placa_veiculo,
                            'modelo_veiculo': motorista.modelo_veiculo,
                            'cor_veiculo': motorista.cor_veiculo,
                            'telefone': user.telefone,
                            'avaliacao_media': float(motorista.avaliacao_media),
                            'nome_completo': user.get_full_name()
                        }
                    except Exception as e:
                        print(f"Erro ao obter dados do motorista: {str(e)}")
                        pass
                    
                    return Response(response_data)
                else:
                    print(f"[DEBUG] Login motorista - falha na autenticação para CPF: {cpf}")
                    return Response(
                        {"error": "Credenciais inválidas"},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
            except Usuario.DoesNotExist:
                print(f"[DEBUG] Login motorista - usuário não encontrado ou não é motorista: {cpf}")
                return Response(
                    {"error": "Usuário não encontrado ou não é um motorista"},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            print(f"[DEBUG] Login motorista - erros de validação: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)