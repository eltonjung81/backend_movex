# Import the JsonResponse class
from django.http import JsonResponse
from corridas.models import Corrida  # Importar do módulo correto

# ...existing code...

# Define a view function that receives the request
def verificar_corrida_motorista(request):
    # Get cpf_motorista from the request data
    cpf_motorista = request.data.get('cpf')  # For DRF requests
    # Or use request.POST.get('cpf') for regular Django form submissions
    # Or request.GET.get('cpf') for query parameters
    
    # Query for active rides
    corrida = Corrida.objects.filter(
        motorista__cpf=cpf_motorista,
        status='EM_ANDAMENTO'
    ).first()
    
    # Rest of your function...
    
    return JsonResponse({"success": True, "corrida": corrida})  # Or appropriate response

# ...existing code...