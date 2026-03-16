from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Client
from .forms import ClientForm

@login_required
def client_list(request):
    clients = Client.objects.filter(is_active=True).order_by('name')
    paginator = Paginator(clients, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'clients/client_list.html', {'page_obj': page_obj})

@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    sessions = client.session_set.all().order_by('-date_start')[:10]
    
    return render(request, 'clients/client_detail.html', {
        'client': client,
        'sessions': sessions
    })

@login_required
def client_create(request):
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('clients:client_list')
    
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" créé avec succès.')
            return redirect('clients:client_detail', pk=client.pk)
    else:
        form = ClientForm()
    
    return render(request, 'clients/client_form.html', {
        'form': form,
        'title': 'Nouveau client'
    })

@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('clients:client_detail', pk=client.pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" modifié avec succès.')
            return redirect('clients:client_detail', pk=client.pk)
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'clients/client_form.html', {
        'form': form,
        'client': client,
        'title': 'Modifier client'
    })