import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_reset_email(to_email, reset_link):
    """Envoie l'email de reinitialisation de mot de passe via SMTP (SSL).
    Ne leve jamais d'exception vers l'appelant : en cas d'echec on log et on renvoie False,
    pour ne jamais bloquer la reponse HTTP ni reveler d'info technique a l'utilisateur."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    sender_email = os.getenv("SMTP_SENDER_EMAIL", smtp_user)
    sender_name = os.getenv("SMTP_SENDER_NAME", "Airlines Reservation")

    if not all([smtp_host, smtp_user, smtp_pass]):
        print("SMTP non configure (.env incomplet) - email de reinitialisation non envoye")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Réinitialisation de votre mot de passe - Airlines Reservation"
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to_email

    text_body = (
        "Bonjour,\n\n"
        "Vous avez demande la reinitialisation de votre mot de passe sur Airlines Reservation.\n"
        f"Cliquez sur ce lien pour choisir un nouveau mot de passe (valable 30 minutes) :\n{reset_link}\n\n"
        "Si vous n'etes pas a l'origine de cette demande, ignorez simplement cet email : "
        "votre mot de passe actuel reste inchange.\n\n"
        "L'equipe Airlines Reservation"
    )

    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #222;">
      <h2 style="color: #012b47;">Réinitialisation de votre mot de passe</h2>
      <p>Vous avez demandé la réinitialisation de votre mot de passe sur <strong>Airlines Reservation</strong>.</p>
      <p>Ce lien est valable <strong>30 minutes</strong> :</p>
      <p style="text-align: center; margin: 28px 0;">
        <a href="{reset_link}" style="background: linear-gradient(135deg, #01abf3, #0170aa); color: #fff; text-decoration: none; padding: 12px 28px; border-radius: 10px; font-weight: 600;">
          Réinitialiser mon mot de passe
        </a>
      </p>
      <p style="font-size: 13px; color: #888;">
        Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet email :
        votre mot de passe actuel reste inchangé.
      </p>
    </div>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(sender_email, [to_email], msg.as_string())
        return True
    except Exception as e:
        print(f"Erreur envoi email de reinitialisation : {e}")
        return False
