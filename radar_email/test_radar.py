import unittest
from radar_email import radar

class TestRadar(unittest.TestCase):
    def sample(self, title, description):
        return radar.job(title, "Empresa Exemplo", description, "https://example.com/job/123", "Remotive", "compatível pela região declarada", "CLT", "2026-10-28")
    def test_pt_better_than_en(self):
        a = self.sample("Gerente de Projetos de TI", "gestão it il itil sla project service governança processo kpi")
        b = self.sample("Gerente de Projetos de TI", "gestão it il itil sla project service governança processo kpi fluent english required")
        score_a = radar.evaluate(a)[0]
        score_b = radar.evaluate(b)[0]
        self.assertLess(score_b, score_a)
        self.assertNotEqual(score_a, 91)
    def test_remote_disqualification(self):
        a=self.sample("Analista de Dados", "python sql power bi hybrid required")
        self.assertIsNone(radar.evaluate(a))
    def test_salary_benchmark(self):
        a=self.sample("Cientista de Dados", "python analytics machine learning")
        self.assertIn("R$ 10.356", radar.salary_text(a))
    def test_salary_announced(self):
        a=self.sample("Analista de Dados", "sql")
        a["salary"]="R$ 8.000/mês"
        self.assertIn("Salário anunciado",radar.salary_text(a))
    def test_admin_no_false_salary(self):
        a=self.sample("Operations Coordinator", "process operations")
        self.assertIn("não identificada",radar.salary_text(a))
    def test_serper_includes_glassdoor(self):
        from unittest.mock import patch
        calls = []
        def fake(url, **kwargs):
            calls.append(kwargs["payload"]["q"])
            return {"organic": []}
        with patch.dict("os.environ", {"SERPER_API_KEY": "fake-test-key"}):
            with patch.object(radar, "fetch_json", side_effect=fake):
                result = radar.serper_indexed()
        self.assertEqual(result, [])
        self.assertTrue(any("glassdoor.com.br" in q for q in calls))
        self.assertTrue(any("linkedin.com/jobs/view" in q for q in calls))
        self.assertTrue(any("gupy.io/jobs" in q for q in calls))

    def test_indexed_hybrid_excluded(self):
        from unittest.mock import patch
        def fake(url, **kwargs):
            return {"organic": [{"title": "Gerente de Projetos - Remoto",
                "snippet": "Vaga híbrida com presença semanal",
                "link": "https://www.linkedin.com/jobs/view/123456"}]}
        with patch.dict("os.environ", {"SERPER_API_KEY": "fake-test-key"}):
            with patch.object(radar, "fetch_json", side_effect=fake):
                self.assertEqual(radar.serper_indexed(), [])

    def test_freelancer_score_and_budget(self):
        j = radar.job("Automação em Python", "Contratante via Workana",
                      "Preciso dashboard automação Python dados SQL",
                      "https://www.workana.com/job/automacao-python-123",
                      "Freelancer: Workana", "trabalho digital; confirmar execução 100% remota",
                      force_category="Freelancer e projetos")
        self.assertEqual(j["category"], "Freelancer e projetos")
        self.assertIn("Orçamento não divulgado", radar.salary_text(j))
        self.assertIsNotNone(radar.evaluate(j))

    def test_freelance_sources_are_queried(self):
        from unittest.mock import patch
        queries = []
        def fake(url, **kwargs):
            queries.append(kwargs["payload"]["q"])
            return {"organic":[]}
        with patch.dict("os.environ", {"SERPER_API_KEY":"test-key"}):
            with patch.object(radar, "fetch_json", side_effect=fake):
                self.assertEqual(radar.freelance_indexed(),[])
        for domain in ("99freelas.com.br","workana.com","freelancer.com",
                       "fiverr.com","getninjas.com.br","vinteconto.com.br",
                       "br.simplyhired.com","br.jooble.org"):
            self.assertTrue(any(domain in q for q in queries), domain)

    def test_catalog_is_not_mistaken_for_project(self):
        from unittest.mock import patch
        def fake(url, **kwargs):
            return {"organic":[{"title":"Especialista Python - contratação",
                 "snippet":"Oferta de serviço de programação em Python e Excel",
                 "link":"https://www.fiverr.com/someone/python-excel"}]}
        with patch.dict("os.environ", {"SERPER_API_KEY":"test-key"}):
            with patch.object(radar,"fetch_json",side_effect=fake):
                self.assertEqual(radar.freelance_indexed(),[])

    def test_indexed_vacancy_no_longer_discarded(self):
        j = radar.job("Analista de Dados Remoto", "Empresa a confirmar",
                      "vaga remota em Python SQL, Brasil", 
                      "https://www.linkedin.com/jobs/view/4483256026",
                      "Busca indexada: LinkedIn", "remoto indicado no índice; validar anúncio")
        points, note = radar.evaluate(j)
        self.assertGreaterEqual(points, 65)
        self.assertLessEqual(points, 79)
        self.assertIn("PRÉ-TRIAGEM", note)

    def test_freelancer_category_last(self):
        self.assertEqual(list(radar.CATEGORIES)[-1], "Freelancer e projetos")

    def test_schedule_part_time(self):
        j = self.sample("Analista de Suporte N2 remoto", "Service desk ITIL com jornada de meio período")
        self.assertEqual(j["category"], "Suporte técnico e aplicações")
        self.assertEqual(radar.schedule_info(j)[0], "MEIO PERÍODO")

    def test_schedule_flexible_and_night(self):
        a = self.sample("Suporte técnico remoto", "Atendimento com horário flexível e ITIL")
        b = self.sample("Help Desk remoto", "Turno noturno no suporte de sistemas")
        self.assertEqual(radar.schedule_info(a)[0], "HORÁRIO FLEXÍVEL")
        self.assertEqual(radar.schedule_info(b)[0], "HORÁRIO ALTERNATIVO")

    def test_schedule_unknown_without_evidence(self):
        j = self.sample("Analista de Suporte N1", "Atendimento por chamados e ITIL")
        self.assertEqual(radar.schedule_info(j)[0], "NÃO INFORMADO")

    def test_schedule_full_time_is_not_flexible(self):
        j = self.sample("Technical Support Engineer", "Full-time ITIL customer support")
        self.assertEqual(radar.schedule_info(j)[0], "TEMPO INTEGRAL")

    def test_schedule_label_in_report(self):
        j = self.sample("Analista de Suporte N2 remoto", "Meio período e service desk")
        j["score"], j["notes"] = radar.evaluate(j)
        output = radar.report([j], [])
        self.assertIn("[CONCILIAÇÃO MESTRADO]", output)
        self.assertIn("Jornada: MEIO PERÍODO", output)

    def test_html_contains_links_and_highlights(self):
        j = self.sample("Analista de Suporte N2 remoto", "Meio período com service desk")
        j["score"], j["notes"] = radar.evaluate(j)
        markup = radar.render_html([j], ["Remotive: 1 candidato"], preview=True)
        self.assertIn("CONCILIAÇÃO MESTRADO", markup)
        self.assertIn("href=\"https://example.com/job/123\"", markup)
        self.assertIn("MEIO PERÍODO", markup)
        self.assertIn("PRÉVIA", markup)
        self.assertIn("<html", markup)
        self.assertIn("Remotive: 1 candidato", markup)

    def test_html_escapes_untrusted_text(self):
        j = self.sample("Analista de Suporte remoto", "ITIL e chamados")
        j["company"] = "<script>alert(1)</script>"
        j["score"], j["notes"] = radar.evaluate(j)
        markup = radar.render_html([j], [])
        self.assertNotIn("<script>", markup)
        self.assertIn("&lt;script&gt;", markup)

    def test_html_keeps_freelancer_last(self):
        a = self.sample("Analista de Dados", "python sql")
        b = radar.job("Automação em Python", "Cliente", "Excel e Python", "https://example.com/project/22",
                      "Freelancer: Workana", "trabalho digital", force_category="Freelancer e projetos")
        for j in (a,b):
            j["score"], j["notes"] = radar.evaluate(j)
        markup = radar.render_html([b,a],[])
        self.assertLess(markup.index("Dados e negócios</h2>"), markup.index("Freelancer e projetos</h2>"))

    def test_sorting_by_score_then_date_within_group(self):
        def make(title, score, day, cat="Dados e negócios"):
            item = self.sample(title, "SQL e Power BI")
            item["category"] = cat
            item["score"] = score
            item["date"] = day
            return item
        records = [
            make("Analista de Dados remoto A", 75, "2026-10-27"),
            make("Analista de Dados remoto B", 80, "2026-10-25"),
            make("Analista de Dados remoto C", 80, "2026-10-28"),
            make("Analista de Dados remoto D", 80, "não informada"),
            make("Consultor TI remoto", 65, "2026-10-28", "Consultoria"),
        ]
        out = radar.ordered_jobs(records)
        self.assertEqual([j["title"] for j in out if j["category"] == "Dados e negócios"],
                         ["Analista de Dados remoto C", "Analista de Dados remoto B",
                          "Analista de Dados remoto D", "Analista de Dados remoto A"])
        self.assertEqual(out[0]["category"], "Consultoria")

    def test_500_total_not_category_quota(self):
        jobs = []
        for i in range(520):
            job = self.sample(f"Analista de Dados {i}", "SQL")
            job["category"] = "Dados e negócios"
            job["score"] = 70 + (i % 20)
            job["date"] = "2026-10-28"
            jobs.append(job)
        ordered = radar.ordered_jobs(jobs)
        self.assertEqual(len(ordered), 500)
        self.assertEqual(ordered[0]["score"], 89)
        self.assertEqual(sum(j["category"] == "Dados e negócios" for j in ordered), 500)

    def test_published_dates_supported(self):
        self.assertEqual(radar.formatted_date("1793145600"), "28/10/2026")
        self.assertEqual(radar.formatted_date("2026-10-28T09:45:00Z"), "28/10/2026")
        self.assertEqual(radar.formatted_date("2026-10-27"), "27/10/2026")
        self.assertEqual(radar.formatted_date("não informada"), "não informada")

    def test_email_multipart_html_and_text(self):
        from unittest.mock import patch
        class FakeSMTP:
            def __init__(self, *args, **kwargs):
                self.message = None
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def login(self, user, pwd): pass
            def send_message(self, message):
                self.message = message
                self.assertion(message)
            def assertion(self, message):
                self.outer.assertEqual(message.get_content_type(), "multipart/alternative")
                self.outer.assertEqual(
                    [p.get_content_type() for p in message.iter_parts()],
                    ["text/plain", "text/html"])
                self.outer.assertIn("<html", list(message.iter_parts())[1].get_content())
        fake = FakeSMTP()
        fake.outer = self
        with patch.dict("os.environ", {"GMAIL_USER":"remetente@example.com",
                                        "GMAIL_APP_PASSWORD":"senha-teste"}):
            with patch.object(radar.smtplib, "SMTP_SSL", return_value=fake):
                radar.email("Texto simples", "<html><body>HTML</body></html>")

if __name__ == "__main__":
    unittest.main()
