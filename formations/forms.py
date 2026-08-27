from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum
from .models import (
    Formation,
    Category,
    Branch,
    Specialty,
    Session,
    Participant,
    TrainerPayment,
)
from resources.models import Trainer, Room, Equipment, PedagogicalAsset
from clients.models import Client


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = [
            "abbreviation",
            "name",
            "name_ar",
            "curriculum_type",
            "curriculum_min_months",
            "curriculum_max_months",
        ]
        widgets = {
            "abbreviation": forms.TextInput(
                attrs={"class": "form-control", "style": "text-transform:uppercase;"}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "name_ar": forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
            "curriculum_type": forms.Select(attrs={"class": "form-select"}),
            "curriculum_min_months": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "curriculum_max_months": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
        }

    def clean_abbreviation(self):
        abbr = self.cleaned_data["abbreviation"].upper().strip()
        if (
            Branch.objects.filter(abbreviation=abbr)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("Cette abréviation existe déjà.")
        return abbr

    def clean(self):
        cleaned_data = super().clean()
        # Re-run model-level curriculum-range validation against submitted data
        instance = Branch(
            abbreviation=cleaned_data.get("abbreviation") or "",
            curriculum_type=cleaned_data.get("curriculum_type"),
            curriculum_min_months=cleaned_data.get("curriculum_min_months"),
            curriculum_max_months=cleaned_data.get("curriculum_max_months"),
        )
        try:
            instance.clean()
        except ValidationError as e:
            raise ValidationError(e.messages)
        return cleaned_data


class SpecialtyForm(forms.ModelForm):
    class Meta:
        model = Specialty
        fields = ["branch", "code", "title", "title_ar"]
        widgets = {
            "branch": forms.Select(attrs={"class": "form-select"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "title_ar": forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        branch = cleaned_data.get("branch")
        code = (cleaned_data.get("code") or "").strip()
        if branch and code:
            if (
                Specialty.objects.filter(branch=branch, code=code)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise ValidationError("Ce code existe déjà pour cette branche.")
        return cleaned_data


class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = [
            "title",
            "title_ar",
            "code",
            "category",
            "specialty",
            "description",
            "duration_days",
            "duration_hours",
            "min_participants",
            "max_participants",
            "evaluation_type",
            "passing_score",
            "max_score",
            "min_attendance_days",
            "produces_certificate",
            "accreditation_body",
            "legal_references",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "title_ar": forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "specialty": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Markdown supporté : **gras**, *italique*, listes, liens...",
                }
            ),
            "duration_days": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "duration_hours": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "min_participants": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "max_participants": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "evaluation_type": forms.Select(attrs={"class": "form-select"}),
            "passing_score": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "max_score": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "min_attendance_days": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "produces_certificate": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "accreditation_body": forms.TextInput(attrs={"class": "form-control"}),
            "legal_references": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Spec §2.1 — code is auto-derived once a specialty is set, so it's
        # only mandatory for specialty-less (freely-coded) formations.
        self.fields["code"].required = False

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").upper().strip()
        specialty = self.data.get("specialty")
        if not code and not specialty:
            raise ValidationError("Le code est requis en l'absence de spécialité.")
        if code and not specialty:
            if (
                Formation.objects.filter(code=code)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise ValidationError("Ce code existe déjà.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        specialty = cleaned_data.get("specialty")
        if specialty:
            # Auto-derive; overrides any freely-typed code/attestation_type.
            cleaned_data["code"] = specialty.reference_root
            cleaned_data["attestation_type"] = specialty.branch.attestation_type
            # Category and specialty are mutually exclusive ways of
            # catalog­ing a formation (see formation_form.html JS, which
            # locks whichever field isn't chosen) — enforced here too so
            # the rule holds even without JS.
            cleaned_data["category"] = None
        elif cleaned_data.get("category"):
            cleaned_data["specialty"] = None
        min_p = cleaned_data.get("min_participants")
        max_p = cleaned_data.get("max_participants")
        if min_p and max_p and min_p > max_p:
            raise ValidationError("Le minimum ne peut pas être supérieur au maximum.")
        passing = cleaned_data.get("passing_score")
        max_s = cleaned_data.get("max_score")
        if passing is not None and max_s is not None and passing > max_s:
            raise ValidationError(
                "La note de passage ne peut pas dépasser la note maximale."
            )
        duration = cleaned_data.get("duration_days")
        min_att = cleaned_data.get("min_attendance_days")
        if duration and min_att and min_att > duration:
            raise ValidationError(
                "La présence minimale ne peut pas dépasser la durée de la formation."
            )
        return cleaned_data


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            "formation",
            "client",
            "trainer",
            "date_start",
            "date_end",
            "location_type",
            "room",
            "external_location",
            "equipment",
            "capacity",
            "specialty_code",
            "session_number",
            "reference",
            "pv_number",
            "mission_order_number",
            "base_price",
            "price_mode",
            "invoice_reference",
            "trainer_cost_mode",
            "trainer_cost_percentage",
            "trainer_cost_amount",
            "committee_members",
        ]
        widgets = {
            "formation": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "trainer": forms.Select(attrs={"class": "form-select"}),
            "date_start": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "date_end": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "location_type": forms.Select(attrs={"class": "form-select"}),
            "room": forms.Select(attrs={"class": "form-select"}),
            "external_location": forms.TextInput(attrs={"class": "form-control"}),
            "equipment": forms.CheckboxSelectMultiple(),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "specialty_code": forms.TextInput(attrs={"class": "form-control"}),
            "session_number": forms.TextInput(attrs={"class": "form-control"}),
            "reference": forms.TextInput(
                attrs={"class": "form-control", "style": "font-family:monospace;"}
            ),
            "pv_number": forms.TextInput(
                attrs={"class": "form-control", "style": "font-family:monospace;"}
            ),
            "mission_order_number": forms.TextInput(
                attrs={"class": "form-control", "style": "font-family:monospace;"}
            ),
            "base_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "price_mode": forms.Select(attrs={"class": "form-select"}),
            "invoice_reference": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex : FA-2026-010"}
            ),
            "trainer_cost_mode": forms.Select(attrs={"class": "form-select"}),
            "trainer_cost_percentage": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "max": "100",
                }
            ),
            "trainer_cost_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
        }

    def __init__(self, *args, **kwargs):
        # `user` is only used to gate the pv_number/mission_order_number
        # hard-coding fields to admins — never required by callers that
        # don't need that check (e.g. session_create, which never shows
        # them anyway since the session doesn't exist yet).
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["formation"].queryset = Formation.objects.filter(is_active=True)
        self.fields["client"].queryset = Client.objects.filter(is_active=True)
        self.fields["trainer"].queryset = Trainer.objects.filter(
            is_active=True
        ).prefetch_related("qualifications")
        self.fields["room"].queryset = Room.objects.filter(is_active=True)
        self.fields["room"].required = False
        self.fields["external_location"].required = False
        self.fields["equipment"].queryset = Equipment.objects.filter(status="available")
        self.fields["equipment"].required = False
        # committee_members not shown in form; managed separately
        self.fields.pop("committee_members", None)

        self.fields["reference"].required = False
        self.fields["pv_number"].required = False
        self.fields["mission_order_number"].required = False

        # reference / pv_number / mission_order_number are the hard-coded
        # overrides for this session's main reference, PV number, and ordre
        # de mission number — see Session.save()'s relaxed protection
        # (clearing is blocked, an explicit new value from an admin is
        # always honoured). They only make sense once the session (and
        # therefore its documents) exist, and only an admin should be able
        # to override what gets printed.
        is_admin = bool(
            user and getattr(user, "profile", None) and user.profile.is_admin()
        )
        if not self.instance.pk or not is_admin:
            self.fields.pop("reference", None)
            self.fields.pop("pv_number", None)
            self.fields.pop("mission_order_number", None)

        if self.instance.pk and self.instance.formation_id:
            self.fields["capacity"].initial = self.instance.formation.max_participants

    def clean(self):
        cleaned_data = super().clean()
        location_type = cleaned_data.get("location_type")
        room = cleaned_data.get("room")
        external_location = cleaned_data.get("external_location")

        if location_type == "institute" and not room:
            raise ValidationError(
                "Une salle doit être sélectionnée pour une formation à l'institut."
            )
        if location_type == "on_site" and not external_location:
            raise ValidationError("Le lieu externe doit être spécifié.")

        date_start = cleaned_data.get("date_start")
        date_end = cleaned_data.get("date_end")
        if date_start and date_end and date_end < date_start:
            raise ValidationError("La date de fin doit être après la date de début.")
        return cleaned_data

    def clean_reference(self):
        """
        Spec — a hard-coded reference that collides with another session
        (e.g. because the formation's specialty/codification or the
        session number was changed after the reference was first
        generated) is auto-corrected to the next free number in the same
        "{prefix}-{counter}/{year}" scheme, rather than blocking the save
        with a hard "already exists" error. `session_create`/`session_edit`
        surface a message when this happened (see `_reference_auto_corrected`
        below) so the correction is never silent.

        A reference that doesn't match the standard scheme (a fully
        custom value an admin typed by hand) can't be safely bumped —
        that case still raises, same as Django's default unique
        validation would.
        """
        reference = (self.cleaned_data.get("reference") or "").strip()
        self._reference_auto_corrected = None
        if not reference:
            return reference

        qs = Session.objects.filter(reference=reference)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if not qs.exists():
            return reference

        from .utils import next_available_session_reference, parse_session_reference

        parsed = parse_session_reference(reference)
        if not parsed:
            raise ValidationError("Un objet Session avec ce champ Référence existe déjà.")

        prefix, _counter, year = parsed
        corrected = next_available_session_reference(
            prefix, year, exclude_pk=self.instance.pk or None
        )
        self._reference_auto_corrected = (reference, corrected)
        return corrected


class TrainerPaymentForm(forms.ModelForm):
    """Spec §new — records one installment towards the formateur's part
    for a terminated session cycle: amount, statut, settlement mode,
    transaction reference (auto-defaulted for espèce if left blank), and
    an optional scanned proof of payment. Also used, unchanged, to *edit*
    an existing installment from the trainer's payment history (admin
    only) — the `session` kwarg is only needed for validating the amount
    and defaulting the initial one on creation."""

    class Meta:
        model = TrainerPayment
        fields = [
            "amount",
            "status",
            "payment_mode",
            "reference",
            "proof_document",
            "notes",
        ]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "payment_mode": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ex : ESP-DUPONT-20260813-143000",
                    "style": "font-family:monospace;",
                }
            ),
            "proof_document": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
            ),
            "notes": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Note interne (optionnel)",
                }
            ),
        }

    def __init__(self, *args, session=None, **kwargs):
        self.session = session or (
            kwargs.get("instance").session if kwargs.get("instance") else None
        )
        super().__init__(*args, **kwargs)
        self.fields["reference"].required = False
        self.fields["notes"].required = False
        if session is not None and not self.instance.pk:
            balance = session.trainer_payment_balance
            if balance:
                self.fields["amount"].initial = balance

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("payment_mode")
        reference = (cleaned_data.get("reference") or "").strip()
        if mode == "espece" and not reference:
            trainer = self.session.trainer if self.session else None
            reference = TrainerPayment.generate_espece_reference(trainer)
        elif not reference:
            self.add_error(
                "reference",
                "La référence de transaction est requise pour ce mode de règlement.",
            )
        cleaned_data["reference"] = reference

        amount = cleaned_data.get("amount")
        status = cleaned_data.get("status")
        if amount is not None and status == "confirmed" and self.session is not None:
            cost = self.session.trainer_cost
            if cost is not None:
                others_total = self.session.trainer_payments.filter(
                    status="confirmed"
                ).exclude(pk=self.instance.pk).aggregate(s=Sum("amount"))[
                    "s"
                ] or Decimal(
                    "0.00"
                )
                if others_total + amount > cost:
                    remaining = cost - others_total
                    self.add_error(
                        "amount",
                        f"Le montant dépasse le solde restant dû ({remaining:.2f} DA "
                        f"sur {cost:.2f} DA au total).",
                    )
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.reference = self.cleaned_data["reference"]
        if self.session is not None and not instance.session_id:
            instance.session = self.session
        if commit:
            instance.save()
        return instance


class SessionAssetDeliveryForm(forms.Form):
    """Spec §new — deliver (consume) pedagogical assets (IT/office/other
    consumables) to a session. Hard-guarded against insufficient stock in
    the view (`PedagogicalAsset.deliver`)."""

    asset = forms.ModelChoiceField(
        queryset=PedagogicalAsset.objects.none(),
        label="Actif pédagogique",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantité livrée",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )
    unit_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Prix unitaire (optionnel)",
        help_text="Laisser vide pour reprendre le prix unitaire actuel de l'actif.",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "step": "0.01"}
        ),
    )
    note = forms.CharField(
        required=False,
        label="Note",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = PedagogicalAsset.objects.filter(
            is_active=True
        ).select_related("category")


class SessionAssetReturnForm(forms.Form):
    """Spec §new — return part of what was delivered to this session
    (surplus not consumed, wrong item...). Increases the asset's stock
    back and is logged as a distinct 'return' movement tied to the
    session."""

    asset = forms.ModelChoiceField(
        queryset=PedagogicalAsset.objects.none(),
        label="Actif pédagogique",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantité retournée",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )
    note = forms.CharField(
        required=False,
        label="Motif du retour",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = PedagogicalAsset.objects.filter(
            is_active=True
        ).select_related("category")


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "gender",
            "date_of_birth",
            "place_of_birth",
            "place_of_birth_ar",
            "job_title",
            "employer",
            "employer_client",
            "phone",
            "email",
            "notes",
            "qr_payload",
            "certificate_number",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "last_name_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "place_of_birth": forms.TextInput(attrs={"class": "form-control"}),
            "place_of_birth_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "employer": forms.TextInput(attrs={"class": "form-control"}),
            "employer_client": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "qr_payload": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Laisser vide pour le lien de vérification par défaut",
                }
            ),
            "certificate_number": forms.TextInput(
                attrs={"class": "form-control", "style": "font-family:monospace;"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        # `user` is only used to gate the certificate_number hard-coding
        # field to admins — see ParticipantForm docstring below.
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["employer_client"].queryset = Client.objects.filter(is_active=True)
        self.fields["employer_client"].required = False
        self.fields["certificate_number"].required = False
        # New participant: default their employer to the client the
        # session was booked for (still fully editable/clearable — this
        # is only a starting value, e.g. for an inter-entreprise session
        # with participants from elsewhere).
        if not self.instance.pk and self.session and self.session.client_id:
            self.fields["employer_client"].initial = self.session.client_id
            if not self.initial.get("employer"):
                self.fields["employer"].initial = self.session.client.name

        # certificate_number is the hard-coded override for this
        # participant's attestation number — see Participant.save()'s
        # relaxed protection (clearing is blocked, an explicit new value
        # from an admin is always honoured). Only makes sense once the
        # participant already exists (Spec §15.2 — never assignable at
        # creation), and only an admin should be able to override what
        # gets printed.
        is_admin = bool(
            user and getattr(user, "profile", None) and user.profile.is_admin()
        )
        if not self.instance.pk or not is_admin:
            self.fields.pop("certificate_number", None)

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        first_name_ar = cleaned_data.get("first_name_ar")
        last_name_ar = cleaned_data.get("last_name_ar")

        has_fr = bool(first_name and last_name)
        has_ar = bool(first_name_ar and last_name_ar)
        # Spec — français/latin and arabe are each fully optional, but at
        # least one COMPLETE pair must be given; neither language is
        # obligatory on its own. (Also enforced in Participant.clean() as
        # defense-in-depth for non-form paths — checked once here so the
        # message doesn't appear twice on this form.)

        if self.session and has_fr:
            existing = Participant.objects.filter(
                session=self.session,
                first_name=first_name,
                last_name=last_name,
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    "Un participant avec ce nom existe déjà dans cette session."
                )
        if self.session and has_ar:
            existing_ar = Participant.objects.filter(
                session=self.session,
                first_name_ar=first_name_ar,
                last_name_ar=last_name_ar,
            ).exclude(pk=self.instance.pk)
            if existing_ar.exists():
                raise ValidationError(
                    "Un participant avec ce nom (arabe) existe déjà dans cette session."
                )
        return cleaned_data


class ExamScoreForm(forms.Form):
    """Bulk exam score entry form for all primary-session participants.

    Spec — the final exam mark defaults to the average of the theory and
    practice marks (themselves entered once, after the formation ends —
    see `ScoreForm`/`session_scores`), but stays fully editable: the
    trainer/admin can override it before saving.
    """

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session:
            max_score = float(self.session.formation.max_score)
            for participant in self.session.participant_set.filter(
                attended=True
            ).order_by("last_name", "first_name"):
                if participant.exam_score is not None:
                    default_score = participant.exam_score
                elif (
                    participant.score_theory is not None
                    and participant.score_practice is not None
                ):
                    default_score = round(
                        (participant.score_theory + participant.score_practice) / 2,
                        2,
                    )
                else:
                    default_score = (
                        participant.score_theory or participant.score_practice
                    )
                self.fields[f"exam_{participant.id}"] = forms.DecimalField(
                    label=participant.full_name,
                    max_digits=5,
                    decimal_places=2,
                    min_value=0,
                    max_value=max_score,
                    required=False,
                    initial=default_score,
                    widget=forms.NumberInput(
                        attrs={
                            "class": "form-control score-input",
                            "step": "0.25",
                            "placeholder": f"/ {max_score:g}",
                        }
                    ),
                )


class SessionStatusForm(forms.Form):
    new_status = forms.ChoiceField(
        choices=Session.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cancellation_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session:
            valid = [
                (s, l)
                for s, l in Session.STATUS_CHOICES
                if self.session.can_transition_to(s)
            ]
            self.fields["new_status"].choices = valid

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get("new_status")
        cancellation_reason = cleaned_data.get("cancellation_reason")
        if new_status == "cancelled" and not cancellation_reason:
            raise ValidationError("Une raison d'annulation est requise.")
        if self.session and not self.session.can_transition_to(new_status):
            raise ValidationError(f"Transition vers '{new_status}' non autorisée.")
        return cleaned_data


class AttendanceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session:
            for participant in self.session.participant_set.all():
                self.fields[f"participant_{participant.id}"] = forms.BooleanField(
                    label=participant.full_name,
                    required=False,
                    initial=participant.attended,
                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                )


class ScoreForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session:
            eval_type = self.session.formation.evaluation_type
            max_score = float(self.session.formation.max_score)
            for participant in self.session.participant_set.all():
                if eval_type in ["theory_only", "both"]:
                    # Single-criterion (theory_only) formations: if the day
                    # mark was never entered but a final exam score already
                    # was (e.g. entered directly via the "Examen" page),
                    # show that as the starting value instead of blank —
                    # it's the same underlying assessment for a theory_only
                    # formation. "both" formations keep no fallback since
                    # the exam score can't be unambiguously split in two.
                    theory_initial = participant.score_theory
                    if theory_initial is None and eval_type == "theory_only":
                        theory_initial = participant.exam_score
                    self.fields[f"theory_{participant.id}"] = forms.DecimalField(
                        label=f"{participant.full_name} - Théorique",
                        max_digits=5,
                        decimal_places=2,
                        min_value=0,
                        max_value=max_score,
                        required=False,
                        initial=theory_initial,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control", "step": "0.25"}
                        ),
                    )
                if eval_type in ["practice_only", "both"]:
                    practice_initial = participant.score_practice
                    if practice_initial is None and eval_type == "practice_only":
                        practice_initial = participant.exam_score
                    self.fields[f"practice_{participant.id}"] = forms.DecimalField(
                        label=f"{participant.full_name} - Pratique",
                        max_digits=5,
                        decimal_places=2,
                        min_value=0,
                        max_value=max_score,
                        required=False,
                        initial=practice_initial,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control", "step": "0.25"}
                        ),
                    )


class ParticipantImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".csv,.xlsx,.xls"}
        )
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file:
            name = file.name.lower()
            if not (
                name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")
            ):
                raise ValidationError("Seuls les fichiers CSV et Excel sont acceptés.")
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("Le fichier ne peut pas dépasser 5 Mo.")
        return file
