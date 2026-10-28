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
if __name__ == "__main__":
    unittest.main()
