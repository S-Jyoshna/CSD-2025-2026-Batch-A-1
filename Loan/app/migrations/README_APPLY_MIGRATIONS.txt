Apply these migrations so the new User columns exist in the database.
From the project root (Loan/), with your virtualenv activated:

  python manage.py migrate app

This applies:
  0002_add_user_registration_fields  (full_name, gender, date_of_birth, pan_number, mobile_number, address)
  0003_user_verification_status      (verification_status)

After this, registration will save all form fields correctly.
