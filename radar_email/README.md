# Radar de oportunidades remotas — e-mail automático

Automação em Python executada por GitHub Actions, **segunda a sexta às 8h de Brasília (11h UTC, horário sujeito a atrasos no GitHub Actions)**. Envia relatórios ao endereço cadastrado e evita reapresentar vagas por empresa+cargo.

## Fontes

| Origem | Acesso | Situação |
|---|---|---|
| Remotive | API pública | Padrão, sem chave |
| Himalayas | API pública | Padrão, sem chave |
| Jobicy | API pública | Padrão, sem chave |
| LinkedIn Jobs | Resultados de busca Google via Serper | **Opcional — exige `SERPER_API_KEY`** |
| Gupy | Resultados de busca Google via Serper | **Opcional — exige `SERPER_API_KEY`** |
| Glassdoor | Resultados indexados via Serper (não API privada) | **Opcional — exige `SERPER_API_KEY`** |
| Indeed, Remotar, Lever, Greenhouse | Resultados de busca Google via Serper | **Opcional — exige `SERPER_API_KEY`** |

**Importante:** esta versão não acessa as APIs privadas de LinkedIn/Gupy e **não faz scraping** de páginas com login. A indexação externa não garante acesso a todas as vagas, atualidade ou confirmação da modalidade remota. O leitor de alertas LinkedIn pelo Gmail **não está integrado a esta rotina**: por enquanto, os alertas podem ser analisados separadamente nesta conversa. Os resultados da Serper são aproximações, não acesso direto a bases do LinkedIn, Gupy ou Glassdoor. Quando disponível, o link remete ao anúncio original para conferência. Para ampliar a cobertura brasileira, é necessário cadastrar a chave de pesquisa indexada.

## Configuração

No repositório do perfil, abra **Settings → Secrets and variables → Actions** e defina:

- `GMAIL_USER`: endereço da conta Gmail remetente.
- `GMAIL_APP_PASSWORD`: senha de aplicativo do Google, nunca a senha normal da conta.
- `SERPER_API_KEY` (**opcional, recomendado**): chave de https://serper.dev para buscar anúncios indexados de LinkedIn, Gupy e outras fontes. O serviço possui franquia gratuita de avaliação e planos pagos; confira os limites da conta antes de habilitar. A implementação faz até 24 consultas indexadas por execução.

Para testar: **Actions → Radar remoto por e-mail → Run workflow**. O script não reenvia o relatório se a data atual já estiver registrada em `vistos.json`.

## Conferir o relatório sem enviar e-mail nem consumir o histórico

Acesse **Actions → Radar remoto por e-mail → Run workflow**, com branch `main`. Escolha:

- **`previa_novas` (padrão):** busca vagas que ainda não constam em `vistos.json`, salva relatório em arquivo. Não envia e-mail e não modifica o histórico. Pode retornar nenhuma vaga nova após um envio recente.
- **`previa_demonstracao`:** busca anúncios atuais incluindo aqueles já apresentados; útil para validar visualmente campos, categorias, salário e notas. **Não representa a reprodução do e-mail anteriormente enviado.** Não envia e-mail, não altera o histórico.
- **`enviar`:** comportamento normal, com envio SMTP e atualização do histórico apenas em caso de envio; se já houve envio na mesma data, não reenvia.

Abra a execução concluída e baixe o artefato **`previa-radar`** em *Artifacts*, na parte inferior da página *Summary*. Ele contém `previa_radar.html` (abrir no navegador) e `previa_radar.txt` (texto simples), disponíveis por sete dias. Para prévias, a etapa de `git push` não é executada.

**Não use `Re-run jobs` em execuções antigas** para conferir atualizações: o GitHub reutiliza o commit original. Inicie um `Run workflow` novo na branch `main`.


## Projetos freelancer

Nova categoria: Python, SQL, dados, Power BI, automação, IA, consultoria e treinamentos. Fontes indexadas via Serper: 99Freelas, Workana, Freelancer.com, Fiverr, Vinteconto, GetNinjas, SimplyHired Brasil e Jooble Brasil. As duas últimas são agregadores de vagas, não marketplaces de projetos. Catálogos de prestadores não são considerados oportunidades automaticamente. A busca não acessa áreas privadas das plataformas; resultados públicos podem estar incompletos ou expirados. Validar orçamento, taxa, escopo e modalidade remota antes de enviar proposta. Sem preço divulgado, o sistema informa que o orçamento é desconhecido, sem inventar média por projeto. Não há cotas por fonte ou categoria. O limite de segurança é de 500 vagas por relatório. Dentro de cada categoria, a classificação é por nota decrescente e, em empate, data de publicação mais recente primeiro.

## Relatório HTML

Os e-mails passam a usar formato **multipart/alternative**: corpo HTML responsivo com cards por vaga, fonte, nota, destaque para jornada conciliável, remuneração e link clicável **Ver oportunidade**, com versão texto simples para clientes que não aceitam HTML. Os dados externos são escapados no HTML. No modo de prévia, o artefato contém `.html` e `.txt`, sem envio e sem alterar o controle de duplicidades.

## Jornada e conciliação com o mestrado

O radar também pesquisa **suporte técnico e aplicações em níveis N1, N2 e N3**, service desk, help desk, suporte de sistemas e atendimento técnico. Cada vaga mostra um campo **Jornada** com evidência textual: **MEIO PERÍODO**, **HORÁRIO FLEXÍVEL**, **HORÁRIO ALTERNATIVO**, **ESCALA A CONFIRMAR**, **TEMPO INTEGRAL** ou **NÃO INFORMADO**. As três primeiras recebem a marca **[CONCILIAÇÃO MESTRADO]** e um pequeno bônus na nota. Jornada não mencionada não é tratada como flexível. Turnos noturnos, finais de semana e escalas precisam de conferência quanto à compatibilidade real; o sistema não presume conveniência. Quando o texto é apenas o resumo indexado, a classificação também é preliminar. A pesquisa continua restrita a vagas remotas, com prioridades brasileiras e freelancers ao final.

## Classificação

Prioridades: **português e regime CLT**, desde que a vaga seja remota, mas também são consideradas oportunidades em inglês, PJ, temporárias, de consultoria, docência e tutoria. Os anúncios em inglês sofrem redução moderada da nota; exigência explícita de fluência gera desconto maior e **deve ser verificada como possível requisito eliminatório**. A nota é uma triagem preliminar feita por regras de palavras-chave, **não é confirmação de requisitos atendidos**.

A seleção não utiliza limites por fonte ou categoria; mantém um teto geral de 500 vagas. Dentro de cada categoria, ordena por nota de aderência decrescente e data de publicação mais recente como desempate. Datas ausentes ou inválidas vêm por último em caso de empate. Freelancer permanece a última categoria. Essa divisão é uma preferência de exibição: os resultados indexados ainda exigem confirmação no anúncio original. O relatório informa a quantidade exibida por fonte.

As notas variam com a compatibilidade da descrição, requisitos e idioma, em vez de atribuir 91/100 a todos os resultados. Publicações híbridas e presenciais explicitamente obrigatórias são excluídas quando detectadas. Em resultados de busca indexada, a modalidade remota **não fica confirmada** apenas pelo título/snippet; a nota é penalizada e o anúncio deve ser lido antes da candidatura.

## Salários e fontes

Quando o anúncio divulga salário, ele é exibido como **salário anunciado**. Caso não divulgue, o e-mail mostra uma referência **média de mercado por área/cargo**, identificada como **salário base CLT — não é salário oferecido**, usando o [Portal Salário](https://www.salario.com.br/) e dados do Novo CAGED atualizados em **08/10/2026**.

| Perfil de referência | Média Brasil/mês | Jornada | Fonte |
|---|---:|---:|---|
| Professor de Informática no Ensino Superior | R$ 6.364 | 26 h/semana | https://www.salario.com.br/profissao/professor-de-informatica-no-ensino-superior-cbo-234120/ |
| Consultor de Tecnologia da Informação | R$ 8.458 | 42 h/semana | https://www.salario.com.br/profissao/consultor-de-tecnologia-da-informacao-cbo-212405/ |
| Gerente de Projetos de TI | R$ 14.040 | 42 h/semana | https://www.salario.com.br/profissao/gerente-de-projetos-de-tecnologia-da-informacao-cbo-142520/ |
| Analista de Business Intelligence | R$ 5.760 | 42 h/semana | https://www.salario.com.br/profissao/analista-de-bi-business-intelligence/ |
| Cientista de Dados | R$ 10.356 | 42 h/semana | https://www.salario.com.br/profissao/cientista-de-dados-data-scientist/ |

São **benchmarks aproximados por família profissional**, não cálculos específicos de cada anúncio, senioridade ou contratação PJ. Para tutoria horista/freelance, a média CLT docente não deve ser tomada como remuneração da vaga. Onde não houver benchmark comparável, isso é informado.

## Deduplicação e envio

O arquivo `vistos.json` contém o registro das combinações empresa+cargo já enviadas, inclusive as vagas do primeiro radar de 27/10/2026. O estado só é atualizado após a confirmação de envio SMTP. A deduplicação por título e empresa é conservadora e pode confundir novas seleções de um mesmo cargo; conferência posterior pode ser necessária.

O radar do GitHub é **independente do radar de pesquisa do ChatGPT**, que pode utilizar investigação mais abrangente. Não há candidatura automática.

## Verificação e execução local

```bash
python -m unittest radar_email.test_radar -v
python -m py_compile radar_email/radar.py
```

O GitHub Actions executa esses testes em alterações do código. Para enviar e-mail, são necessários os secrets. Não armazene segredos no repositório e não compartilhe credenciais no chat.
