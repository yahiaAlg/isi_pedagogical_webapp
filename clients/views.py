from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from .models import Client
from .forms import ClientForm

# 'sessions_total' avoids clash with @property session_count on Client model
VALID_SORT_MAP = {
    "name": "name",
    "city": "city",
    "contact_person": "contact_person",
    "session_count": "sessions_total",
}


@login_required
def client_list(request):
    sort = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort not in VALID_SORT_MAP:
        sort = "name"
    db_field = VALID_SORT_MAP[sort]
    qs = Client.objects.filter(is_active=True).annotate(sessions_total=Count("session"))

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(name_ar__icontains=q)
            | Q(contact_person__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(nif__icontains=q)
            | Q(nis__icontains=q)
            | Q(rc__icontains=q)
        )
    city = request.GET.get("city", "").strip()
    if city:
        qs = qs.filter(city__icontains=city)
    sessions_min = request.GET.get("sessions_min", "").strip()
    if sessions_min.isdigit():
        qs = qs.filter(sessions_total__gte=int(sessions_min))
    sessions_max = request.GET.get("sessions_max", "").strip()
    if sessions_max.isdigit():
        qs = qs.filter(sessions_total__lte=int(sessions_max))
    created_from = request.GET.get("created_from", "").strip()
    if created_from:
        qs = qs.filter(created_at__date__gte=created_from)
    created_to = request.GET.get("created_to", "").strip()
    if created_to:
        qs = qs.filter(created_at__date__lte=created_to)

    qs = qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))

    cities = (
        Client.objects.filter(is_active=True)
        .exclude(city="")
        .order_by("city")
        .values_list("city", flat=True)
        .distinct()
    )

    return render(
        request,
        "clients/client_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
            "cities": cities,
            "filters": {
                "q": q,
                "city": city,
                "sessions_min": sessions_min,
                "sessions_max": sessions_max,
                "created_from": created_from,
                "created_to": created_to,
            },
        },
    )


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    sessions = client.session_set.all().order_by("-date_start")[:10]
    return render(
        request, "clients/client_detail.html", {"client": client, "sessions": sessions}
    )


@login_required
def client_create(request):
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("clients:client_list")
    if request.method == "POST":
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" créé avec succès.')
            return redirect("clients:client_detail", pk=client.pk)
    else:
        form = ClientForm()
    return render(
        request, "clients/client_form.html", {"form": form, "title": "Nouveau client"}
    )


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("clients:client_detail", pk=client.pk)
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Client "{client.name}" modifié avec succès.')
            return redirect("clients:client_detail", pk=client.pk)
    else:
        form = ClientForm(instance=client)
    return render(
        request,
        "clients/client_form.html",
        {"form": form, "client": client, "title": "Modifier client"},
    )


@login_required
def client_delete(request, pk):
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("clients:client_list")
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        name = client.name
        client.delete()
        messages.success(request, f'Client "{name}" supprimé.')
    return redirect("clients:client_list")
