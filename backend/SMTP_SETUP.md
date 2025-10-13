## SMTP Setup for Fast OTP Email Delivery

To enable fast and secure OTP email sending, set the following environment variables in your backend deployment:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
```

Use an app password for Gmail (not your regular password). See [Google App Passwords](https://support.google.com/accounts/answer/185833) for setup.

Restart the backend after updating these variables.
