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

Abra a execução concluída e baixe o artefato **`previa-radar`** em *Artifacts*, na parte inferior da página *Summary*. Ele contém `previa_radar.txt` e fica disponível por sete dias. Para prévias, a etapa de `git push` não é executada.

**Não use `Re-run jobs` em execuções antigas** para conferir atualizações: o GitHub reutiliza o commit original. Inicie um `Run workflow` novo na branch `main`.

## Classificação

Prioridades: **português e regime CLT**, desde que a vaga seja remota, mas também são consideradas oportunidades em inglês, PJ, temporárias, de consultoria, docência e tutoria. Os anúncios em inglês sofrem redução moderada da nota; exigência explícita de fluência gera desconto maior e **deve ser verificada como possível requisito eliminatório**. A nota é uma triagem preliminar feita por regras de palavras-chave, **não é confirmação de requisitos atendidos**.

A seleção final reserva até 25 vagas aos resultados brasileiros indexados (LinkedIn, Gupy, Glassdoor, Indeed, Remotar e carreiras), complementados por até dez vagas internacionais. Essa divisão é uma preferência de exibição: os resultados indexados ainda exigem confirmação no anúncio original. O relatório informa a quantidade exibida por fonte.

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
