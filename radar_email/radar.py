#!/usr/bin/env python3
"""Radar independente: coleta vagas remotas, deduplica e envia resumo por SMTP."""
import html
import json
import os
import re
import smtplib
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "vistos.json"
EMAIL_TO = "alvarobonifacio1980@gmail.com"
KEYWORDS = {
    "Docência e tutoria": ["teacher", "instructor", "educator", "trainer", "tutor", "professor", "docente", "instructional", "conteudista", "teaching"],
    "Consultoria": ["consultant", "consultor", "implementation", "implantação", "advisory", "advisor"],
    "Gestão e governança TI": ["project manager", "program manager", "delivery manager", "service manager", "it manager", "pmo", "governance", "itil", "operations manager", "gerente de ti", "gerente de projeto", "gerente de serviços"],
    "Dados e negócios": ["data analyst", "business analyst", "analytics", "business intelligence", "power bi", "analista de dados", "analista de negócios"],
    "IA e ciência de dados": ["data scientist", "machine learning", "artificial intelligence", "ai engineer", "cientista de dados", "inteligência artificial"],
    "Administração tecnológica": ["technical operations", "operations coordinator", "administrative", "customer success", "support manager", "coordenação de ti"],
}
EXPERIENCE = ("itil", "governance", "process", "project", "service", "data", "python", "sql", "analytics", "business", "management", "teacher", "train", "financial", "ai", "bpm")
BLOCK = ("on-site", "onsite", "on site", "hybrid", "híbrido", "hibrido", "presencial", "relocation required", "must relocate")
INITIAL_SEEN = [
    "softexpert|consultor de implantação setor financeiro",
    "spread tecnologia|pmo pleno dados ia",
    "softexpert|consultor de implantação setor público",
    "semantix|analista sênior de governança de dados",
]


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "RadarPortfolio/1.0 (+github.com/alvarobonifacio1980)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=35) as res:
        return json.load(res)


def clean(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))).strip()


def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def key(job):
    return normalize(job["company"]) + "|" + normalize(job["title"])


def categorize(title):
    title = title.lower()
    for category, words in KEYWORDS.items():
        if any(w in title for w in words):
            return category
    return ""


def score(job):
    title, description = job["title"].lower(), job["description"].lower()
    base = 70
    base += min(15, sum(3 for w in EXPERIENCE if w in description))
    if any(x in title for x in ("manager", "lead", "senior", "consult", "trainer", "professor", "analyst")):
        base += 6
    if any(x in description for x in ("phd required", "doctorate required", "master's degree required", "mestrado concluído obrigatório", "native english required")):
        return None
    if any(x in description for x in BLOCK):
        return None
    return min(95, base)


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"seen": INITIAL_SEEN, "last_email_date": ""}


def fetch_himalayas():
    jobs = []
    # A API retorna anúncios remotos e restrições geográficas estruturadas.
    for query in ("project manager", "business analyst", "data analyst", "instructor", "consultant", "data scientist", "operations manager"):
        url = "https://himalayas.app/jobs/api/search?" + urllib.parse.urlencode({"q": query, "sort": "recent", "page": 1})
        data = get_json(url)
        for row in data.get("jobs", []):
            countries = [str(x.get("alpha2", "")).upper() for x in row.get("locationRestrictions", []) if isinstance(x, dict)]
            if countries and "BR" not in countries:
                continue
            offsets = row.get("timezoneRestrictions", []) or []
            if offsets and not any("-03" in str(x) or "-3" == str(x) for x in offsets):
                continue
            title = clean(row.get("title"))
            category = categorize(title)
            if not category:
                continue
            link = row.get("applicationLink") or row.get("guid") or ""
            if not link.startswith("https://"):
                continue
            descr = clean(row.get("description") or row.get("excerpt"))
            sal = ""
            if row.get("minSalary") is not None or row.get("maxSalary") is not None:
                sal = f"{row.get('currency') or ''} {row.get('minSalary') or '?'}–{row.get('maxSalary') or '?'} / {row.get('salaryPeriod') or 'ano'} (divulgado)"
            date = datetime.fromtimestamp(int(row.get("pubDate") or 0), tz=timezone.utc).strftime("%d/%m/%Y") if row.get("pubDate") else "não informada"
            jobs.append({"title": title, "company": clean(row.get("companyName")), "category": category, "description": descr, "url": link, "source": "Himalayas", "regime": clean(row.get("employmentType")) or "não informado", "salary": sal or "não divulgado; média de mercado não verificada", "date": date})
    return jobs


def fetch_remotive():
    jobs = []
    data = get_json("https://remotive.com/api/remote-jobs")
    for row in data.get("jobs", []):
        loc = normalize(row.get("candidate_required_location"))
        if loc and not any(w in loc for w in ("worldwide", "anywhere", "global", "brazil", "brasil", "latin america", "latam", "south america")):
            continue
        title = clean(row.get("title"))
        category = categorize(title)
        if not category:
            continue
        descr = clean(row.get("description"))
        link = row.get("url") or ""
        if not link.startswith("https://"):
            continue
        jobs.append({"title": title, "company": clean(row.get("company_name")), "category": category, "description": descr, "url": link, "source": "Remotive", "regime": clean(row.get("job_type")) or "não informado", "salary": clean(row.get("salary")) + " (divulgado)" if row.get("salary") else "não divulgado; média de mercado não verificada", "date": (row.get("publication_date") or "")[:10] or "não informada"})
    return jobs


def format_email(jobs, sources):
    date = datetime.now().strftime("%d/%m/%Y")
    rows = [f"RADAR DE OPORTUNIDADES REMOTAS — {date}", "", "Aderência: triagem heurística preliminar; confirme requisitos e remoto no anúncio.", "CLT preferencial, PJ e projetos aceitos; sem deslocamento presencial recorrente.", ""]
    if not jobs:
        rows.append("Nenhuma vaga nova passou pelos critérios automáticos nesta execução.")
    for category in KEYWORDS:
        group = [j for j in jobs if j["category"] == category]
        if group:
            rows.extend([category.upper(), "-" * 28])
            for j in group:
                rows.extend([f"[{j['score']}/100] {j['title']} — {j['company']}", f"Fonte: {j['source']} | Regime: {j['regime']} | Data: {j['date']}", f"Remoto: anúncio de plataforma remota; localização Brasil/mundo compatível pela fonte; validar condições no texto", f"Remuneração: {j['salary']}", f"Link: {j['url']}", ""])
    rows += ["", "Fontes consultadas: " + "; ".join(sources), "Esta automação usa fontes públicas estruturadas. NÃO inclui LinkedIn/Gupy sem integração própria.", "Dados/links: Himalayas (himalayas.app) e Remotive (remotive.com).", "O relatório é apenas uma triagem: a pontuação não substitui leitura da vaga."]
    return "\n".join(rows)


def send_email(body):
    sender = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not sender or not password:
        raise RuntimeError("Configure os secrets GMAIL_USER e GMAIL_APP_PASSWORD no GitHub.")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = EMAIL_TO
    msg["Subject"] = "Radar de oportunidades remotas — " + datetime.now().strftime("%d/%m/%Y")
    msg.set_content(body)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=40, context=context) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)


def main():
    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_email_date") == today:
        print("Relatório já enviado hoje; não reenviar.")
        return
    sources, found = [], []
    for label, fn in (("Himalayas", fetch_himalayas), ("Remotive", fetch_remotive)):
        try:
            batch = fn()
            sources.append(f"{label}: {len(batch)} anúncios candidatos")
            found.extend(batch)
        except Exception as exc:
            sources.append(f"{label}: falha de consulta ({type(exc).__name__})")
    if not found and not any("anúncios candidatos" in src for src in sources):
        raise RuntimeError("Todas as fontes falharam: não enviar relatório vazio como sucesso.")
    seen = set(state.get("seen", []))
    new = []
    for job in found:
        fingerprint = key(job)
        if fingerprint in seen:
            continue
        value = score(job)
        if value is None or value < 65:
            continue
        job["score"] = value
        seen.add(fingerprint)
        new.append(job)
    new.sort(key=lambda j: (-j["score"], j["category"], j["title"]))
    new = new[:25]
    report = format_email(new, sources)
    print(f"Fontes: {sources}; candidatos novos: {len(new)}")
    # Não registrar como enviados se o SMTP falhar.
    send_email(report)
    state["seen"] = sorted(set(state.get("seen", [])) | {key(j) for j in new})
    state["last_email_date"] = today
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("E-mail enviado com sucesso. Estado de deduplicação atualizado.")


if __name__ == "__main__":
    main()
