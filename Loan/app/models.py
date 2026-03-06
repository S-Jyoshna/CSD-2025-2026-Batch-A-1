from django.db import models

class User(models.Model):
    id = models.IntegerField(auto_created=True, primary_key=True)
    username = models.CharField(max_length=1000, default='')
    password = models.CharField(max_length=1000, default='')
    email = models.CharField(max_length=1000, default='')
    is_approved = models.CharField(max_length=1000)
    is_blocked = models.CharField(max_length=1000)
    status = models.CharField(max_length=20, default='approve')
    profile_pic = models.CharField(max_length=1000, blank=True, default='')
    # Registration fields (backward compatible: existing users get default/blank)
    full_name = models.CharField(max_length=255, blank=True, default='')
    gender = models.CharField(max_length=20, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    # PAN is used as a unique identifier (govt-issued in India); one registration per person, prevents duplicate accounts.
    pan_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True, default='')
    address = models.TextField(blank=True, default='')
    # Separate from status: verification_status controls "under verification" messaging; status is used for APPROVED/pending/BLOCKED by admin.
    verification_status = models.CharField(max_length=30, default='Pending', blank=True)
    # KYC-style verification: store path to uploaded PAN card document (no passwords or sensitive credentials exposed).
    pan_card_document = models.CharField(max_length=500, blank=True, default='')
    # Reason given when admin rejects verification (e.g. invalid document).
    rejection_reason = models.TextField(blank=True, default='')

class Loantable(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    loan_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    customer_name = models.CharField(max_length=100)
    details=models.ForeignKey(User,on_delete=models.CASCADE)
    amount=models.IntegerField()
    duration=models.IntegerField()
    monthlyamount=models.IntegerField()
    loan_details=models.CharField(max_length=1000)
    status = models.CharField(max_length=10, choices=[('Applied', 'Applied'), ('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Active', 'Active'), ('Inactive', 'Inactive'), ('Completed', 'Completed')])
    pan_no = models.CharField(max_length=10)
    gender = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    address = models.TextField()
    mobile_no = models.CharField(max_length=10)
    email = models.EmailField()
    start_date = models.DateField()
    rejection_reason = models.TextField(blank=True, null=True)
    approved_reason= models.TextField(blank=True, null=True)
    payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # --- Extended fields for real-world loan workflow (non-breaking additions) ---
    # Basic loan meta (kept separate from legacy loan_details/status usage).
    loan_type = models.CharField(max_length=50, blank=True, default='')  # Personal/Home/Education/Agriculture
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    farmer_type = models.CharField(max_length=30, blank=True, default='')
    purpose = models.CharField(max_length=500, blank=True, default='')

    # Surety selection (controls which sub-fields are meaningful).
    surety_type = models.CharField(max_length=20, blank=True, default='')  # income / guarantor / asset

    # Income-based surety (applicant)
    income_employment_type = models.CharField(max_length=20, blank=True, default='')
    income_annual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    income_monthly = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    income_employer_name = models.CharField(max_length=255, blank=True, default='')
    income_years_employment = models.IntegerField(null=True, blank=True)
    income_proof_path = models.CharField(max_length=500, blank=True, default='')

    # Guarantor-based surety
    guarantor_name = models.CharField(max_length=255, blank=True, default='')
    guarantor_relationship = models.CharField(max_length=50, blank=True, default='')
    guarantor_pan = models.CharField(max_length=20, blank=True, default='')
    guarantor_mobile = models.CharField(max_length=15, blank=True, default='')
    guarantor_address = models.TextField(blank=True, default='')
    guarantor_employment_type = models.CharField(max_length=20, blank=True, default='')
    guarantor_annual_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    guarantor_monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    guarantor_employer_name = models.CharField(max_length=255, blank=True, default='')
    guarantor_years_employment = models.IntegerField(null=True, blank=True)
    guarantor_income_proof_path = models.CharField(max_length=500, blank=True, default='')

    # Asset-based surety
    asset_type = models.CharField(max_length=20, blank=True, default='')  # Home / Gold / Land / Equipment
    asset_home_address = models.TextField(blank=True, default='')
    asset_home_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    asset_home_proof_path = models.CharField(max_length=500, blank=True, default='')
    asset_gold_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    asset_gold_purity = models.CharField(max_length=20, blank=True, default='')
    asset_gold_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    asset_gold_proof_path = models.CharField(max_length=500, blank=True, default='')
    equipment_type = models.CharField(max_length=100, blank=True, default='')
    equipment_model = models.CharField(max_length=100, blank=True, default='')
    equipment_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    equipment_proof_path = models.CharField(max_length=500, blank=True, default='')
    offline_verification_required = models.BooleanField(default=False)

    # System-generated risk / eligibility summary (hidden from user form).
    risk_score = models.CharField(max_length=20, blank=True, default='')        # Low / Medium / High
    eligibility_status = models.CharField(max_length=30, blank=True, default='')# Eligible / Borderline / Not Eligible
    total_installments = models.IntegerField(default=0)
    paid_installments = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_interest = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_repayable_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_paid_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closed_at = models.DateTimeField(null=True, blank=True)
    
class Transaction(models.Model):
    id=models.IntegerField(auto_created=True,primary_key=True)
    transaction_number = models.PositiveIntegerField(unique=True, null=True, blank=True)
    username = models.ForeignKey(User, on_delete=models.CASCADE)
    loan = models.ForeignKey(Loantable, on_delete=models.CASCADE, null=True)
    monthlyamount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    method = models.CharField(max_length=50)
    transaction_date = models.DateTimeField()
    status = models.CharField(max_length=20, default='Pending')
    installment_number = models.IntegerField(default=0)
    verified_by_admin = models.BooleanField(default=False)
    upi_id = models.CharField(max_length=50, null=True, blank=True)
    card_number = models.CharField(max_length=20, null=True, blank=True)
    wallet_name = models.CharField(max_length=20, null=True, blank=True)
    wallet_number = models.CharField(max_length=20, null=True, blank=True)

class Feedback(models.Model):
    username = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    rating = models.PositiveIntegerField(default=5) 
    submitted_at = models.DateTimeField(auto_now_add=True)









    
