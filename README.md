# 🚀 Space Job Tracker — Guida Setup Completa

Sistema di monitoraggio automatico delle offerte di lavoro in ambito Space Engineering,
con notifiche giornaliere su Telegram.

---

## Struttura del progetto

```
space-job-tracker/
├── scraper.py               ← Script principale
├── companies.json           ← Lista aziende da monitorare (modificabile)
├── seen_jobs.json           ← Generato automaticamente (non toccare)
├── requirements.txt         ← Dipendenze Python
├── .github/
│   └── workflows/
│       └── check_jobs.yml   ← Workflow GitHub Actions
└── README.md
```

---

## STEP 1 — Crea il bot Telegram

1. Apri Telegram e cerca **@BotFather**
2. Manda il messaggio `/newbot`
3. Scegli un nome per il bot (es. `Space Job Tracker`)
4. Scegli uno username (deve finire in `bot`, es. `spacejobtracker_bot`)
5. BotFather ti darà un **token** del tipo:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
   **Salvalo**, ti servirà dopo.

6. Per ottenere il tuo **Chat ID**:
   - Cerca il bot **@userinfobot** su Telegram
   - Mandagli `/start`
   - Ti risponderà con il tuo ID numerico (es. `987654321`)

---

## STEP 2 — Crea il repository GitHub

1. Vai su [github.com](https://github.com) e crea un **nuovo repository**
   - Nome: `space-job-tracker` (o come preferisci)
   - Visibilità: **Private** (consigliato, contiene info sulle tue ricerche)
   - Non inizializzare con README

2. Carica tutti i file del progetto nel repository:
   - Puoi usare GitHub Desktop, VS Code con Git, o il drag & drop direttamente su GitHub

---

## STEP 3 — Aggiungi i secret su GitHub

I token Telegram NON vanno mai scritti nel codice. Vanno salvati come **GitHub Secrets**.

1. Nel repository, vai su **Settings → Secrets and variables → Actions**
2. Clicca **New repository secret** e aggiungi:

   | Name | Value |
   |------|-------|
   | `TELEGRAM_TOKEN` | Il token del bot (da BotFather) |
   | `TELEGRAM_CHAT_ID` | Il tuo Chat ID numerico |

---

## STEP 4 — Configura le aziende da monitorare

Modifica il file `companies.json` con le aziende che ti interessano.

### Tipi di configurazione disponibili:

#### 🟢 Greenhouse (ATS molto comune)
```json
{
  "name": "Rocket Lab",
  "ats": "greenhouse",
  "company_id": "rocketlab",
  "keywords": ["GNC", "AOCS", "simulation"]
}
```
Per trovare il `company_id`: vai sulla career page dell'azienda.
Se l'URL è `https://boards.greenhouse.io/rocketlab` → il company_id è `rocketlab`.

#### 🟢 Lever
```json
{
  "name": "Relativity Space",
  "ats": "lever",
  "company_id": "relativityspace",
  "keywords": ["GNC", "systems"]
}
```
Se l'URL è `https://jobs.lever.co/relativityspace` → il company_id è `relativityspace`.

#### 🟢 SmartRecruiters
```json
{
  "name": "Airbus Defence and Space",
  "ats": "smartrecruiters",
  "company_id": "AirbusDefenceandSpace",
  "keywords": ["GNC", "AOCS"]
}
```
Se l'URL è `https://jobs.smartrecruiters.com/AirbusDefenceandSpace` → il company_id è `AirbusDefenceandSpace`.

#### 🟡 Workday
```json
{
  "name": "ESA",
  "ats": "workday",
  "url": "https://esa.wd3.myworkdayjobs.com/ESA_External_Career_Site",
  "keywords": ["GNC", "AOCS"]
}
```

#### 🟠 Generic (sito custom)
Per siti con HTML custom, hai bisogno del CSS selector del job listing.

**Come trovarlo:**
1. Apri la career page dell'azienda nel browser
2. Premi F12 (DevTools) → vai su "Elements"
3. Clicca sull'icona cursore (in alto a sinistra in DevTools)
4. Clicca su uno dei titoli delle posizioni
5. Nell'HTML evidenziato, guarda il tag e la classe (es. `<a class="job-listing__title">`)
6. Il tuo selector sarà: `a.job-listing__title`

```json
{
  "name": "GMV",
  "ats": "generic",
  "url": "https://www.gmv.com/en-es/company/careers/job-openings",
  "selector": "a.job-title",
  "base_url": "https://www.gmv.com",
  "keywords": ["GNC", "AOCS"]
}
```

### Keywords consigliate per Space GNC/AOCS:
```json
["GNC", "AOCS", "guidance", "navigation", "control", "attitude",
 "systems engineer", "simulation", "spacecraft", "satellite",
 "avionics", "flight dynamics", "orbit", "propulsion"]
```
> Lascia `"keywords": []` per ricevere TUTTE le posizioni aperte di quell'azienda.

---

## STEP 5 — Verifica che funzioni

1. Nel repository GitHub, vai sul tab **Actions**
2. Clicca sul workflow **"Space Job Tracker"**
3. Clicca **"Run workflow"** → **"Run workflow"** (pulsante verde)
4. Controlla i log per vedere se lo script gira correttamente
5. Controlla Telegram — dovresti ricevere le notifiche!

---

## STEP 6 — Orario di esecuzione

Di default lo script gira ogni giorno alle **08:00 ora italiana**.
Per modificarlo, edita la riga `cron` in `.github/workflows/check_jobs.yml`:

```yaml
- cron: "0 7 * * *"   # ogni giorno alle 07:00 UTC = 08:00 ora solare italiana
```

Usa [crontab.guru](https://crontab.guru) per costruire l'orario che preferisci.

---

## Come aggiungere una nuova azienda

1. Identifica quale ATS usa (guarda l'URL della career page)
2. Aggiungi l'entry in `companies.json`
3. Fai commit e push → il prossimo run la includerà

### Come riconoscere l'ATS dall'URL:
| URL contiene | ATS |
|---|---|
| `boards.greenhouse.io/...` | greenhouse |
| `jobs.lever.co/...` | lever |
| `jobs.smartrecruiters.com/...` | smartrecruiters |
| `*.myworkdayjobs.com/...` | workday |
| Tutto il resto | generic |

---

## Troubleshooting

**Lo script non trova posizioni su siti generic:**
→ Il CSS selector potrebbe essere cambiato. Ricontrolla con DevTools.

**Ricevo notifiche duplicate:**
→ Non succede: `seen_jobs.json` tiene traccia di tutti i job già visti.

**Il workflow non parte:**
→ Controlla che i secret `TELEGRAM_TOKEN` e `TELEGRAM_CHAT_ID` siano impostati correttamente.

**Il sito blocca le richieste:**
→ Alcuni siti usano Cloudflare o CAPTCHA. Per questi è necessario un approccio diverso (contattami).

---

## Limitazioni note

- **Workday**: il rendering JS avanzato può rendere lo scraping inaffidabile su alcuni siti.
  Se una company Workday non funziona, puoi spostarla su `generic` con il selector appropriato.
- **Siti con autenticazione**: non supportati.
- **Siti con heavy JS** (React/Angular senza SSR): potrebbero richiedere Playwright (versione avanzata).

---

*Made for Space Engineering job hunting 🛸*
