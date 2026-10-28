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

if __name__ == "__main__":
    unittest.main()
