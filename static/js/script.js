function switchTab(tab) {
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('panel-' + tab).classList.add('active');
      document.querySelectorAll('.tab-pill').forEach(b => {
        b.classList.toggle('active', b.dataset.tab === tab);
      });
    }
const choiceEl = document.getElementById("choice")
if (choiceEl) {
    choiceEl.addEventListener("change", function() {
        if (this.value === "hotel") {
            document.getElementById("dest-hotel").style.display = "block"
            document.getElementById("dest-vol").style.display = "none"
        } else {
            document.getElementById("dest-vol").style.display = "block"
            document.getElementById("dest-hotel").style.display = "none"
        }
    })
}

// ──────────────────────────────────────────────
// Menu déroulant "Mon compte" (profil / déconnexion)
// ──────────────────────────────────────────────
const accountMenu = document.querySelector('.account-menu');
if (accountMenu) {
    const toggle = accountMenu.querySelector('.account-menu__toggle');

    toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        const isOpen = accountMenu.classList.toggle('open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    document.addEventListener('click', function (e) {
        if (!accountMenu.contains(e.target)) {
            accountMenu.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            accountMenu.classList.remove('open');
            toggle.setAttribute('aria-expanded', 'false');
        }
    });
}

// ──────────────────────────────────────────────
// Popup de confirmation (toast) - formulaire de contact
// ──────────────────────────────────────────────
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.setAttribute('role', 'status');
    const icon = type === 'warn' ? 'fa-triangle-exclamation' : 'fa-circle-check';
    toast.innerHTML = '<i class="fa-solid ' + icon + '"></i> ' + message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

if (document.body.dataset.contactSuccess === 'true') {
    showToast('Formulaire envoyé avec succès !');
    const contactForm = document.querySelector('.contact-form-card form');
    if (contactForm) {
        contactForm.reset();
    }
}

// ──────────────────────────────────────────────
// Popup d'avertissement - rate limit dépassé
// ──────────────────────────────────────────────
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('rate_limited') === '1') {
    showToast('Vous avez envoyé trop de demandes, veuillez réessayer plus tard.', 'warn');
    urlParams.delete('rate_limited');
    const cleanQuery = urlParams.toString();
    const newUrl = window.location.pathname + (cleanQuery ? '?' + cleanQuery : '') + window.location.hash;
    window.history.replaceState({}, '', newUrl);
}

// ──────────────────────────────────────────────
// Popup d'erreur - connexion (identifiants incorrects)
// ──────────────────────────────────────────────
if (document.body.dataset.loginError === 'true') {
    showToast('Adresse mail ou mot de passe incorrect.', 'warn');
}

// ──────────────────────────────────────────────
// Popup d'erreur - création de compte (email déjà utilisé)
// ──────────────────────────────────────────────
if (document.body.dataset.signupError === 'email_exists') {
    showToast('Cette adresse mail est déjà utilisée par un compte existant.', 'warn');
} else if (document.body.dataset.signupError === 'password_mismatch') {
    showToast('Les mots de passe ne correspondent pas.', 'warn');
}

// ──────────────────────────────────────────────
// Bandeau cookies (RGPD)
// ──────────────────────────────────────────────
function showCookieBanner() {
    const banner = document.createElement('div');
    banner.className = 'cookie-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Gestion des cookies');
    banner.innerHTML =
        '<p>Ce site utilise uniquement un cookie de session strictement nécessaire à votre connexion. ' +
        'Aucun cookie de suivi ou publicitaire n\'est utilisé. ' +
        '<a href="/confidentialite">En savoir plus</a></p>' +
        '<div class="cookie-banner__actions">' +
        '<button type="button" class="cookie-banner__refuse">Refuser</button>' +
        '<button type="button" class="cookie-banner__accept">Accepter</button>' +
        '</div>';
    document.body.appendChild(banner);

    banner.querySelector('.cookie-banner__accept').addEventListener('click', () => {
        localStorage.setItem('cookie_consent', 'accepted');
        banner.remove();
    });
    banner.querySelector('.cookie-banner__refuse').addEventListener('click', () => {
        localStorage.setItem('cookie_consent', 'refused');
        banner.remove();
    });
}

try {
    if (!localStorage.getItem('cookie_consent')) {
        showCookieBanner();
    }
} catch (e) {
    // localStorage indisponible (navigation privée stricte, etc.) : on n'affiche pas le bandeau
}
