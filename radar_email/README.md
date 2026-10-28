# Radar de oportunidades — envio automático por Gmail

Rotina **independente do ChatGPT** para enviar um resumo diário de vagas novas por e-mail. Executada por **GitHub Actions**, segunda a sexta-feira, aproximadamente às 8h de Brasília (11h UTC); GitHub Actions pode atrasar horários de execução.

## Funcionamento

1. Consulta as APIs públicas [Himalayas](https://himalayas.app/docs/remote-jobs-api) e [Remotive](https://remotive.com/remote-jobs/api).
2. Seleciona títulos relacionados a docência, tutoria, consultoria, gestão, dados, IA e funções administrativas em TI.
3. Filtra vagas por restrições geográficas compatíveis com Brasil/mundo, quando disponibilizadas na fonte. A indicação 'remoto' depende dos metadados da plataforma: **sempre confira o anúncio**.
4. Atribui pontuação **heurística preliminar** (não é a análise de aderência completa do radar do ChatGPT).
5. Remove anúncios já enviados com base na combinação empresa+cargo; registra histórico em `vistos.json`.
6. Envia por SMTP do Gmail para `alvarobonifacio1980@gmail.com` e persiste o histórico **somente após o envio ser confirmado**. Se não houver vagas novas, informa isso por e-mail.

## Configuração indispensável (não coloque senhas em arquivos!)

No repositório GitHub, abra **Settings → Secrets and variables → Actions → New repository secret**:

- `GMAIL_USER`: endereço da conta Gmail remetente.
- `GMAIL_APP_PASSWORD`: **senha de app** de 16 caracteres gerada na conta Google com verificação em duas etapas. Consulte https://myaccount.google.com/apppasswords. Não use sua senha normal do Gmail.

Depois acesse **Actions → Radar remoto por e-mail → Run workflow** para testar. Nenhum envio ocorrerá sem os secrets.

## Limitações claras

- **Não consulta diretamente LinkedIn, Gupy, Indeed, universidades ou outras plataformas.** São necessárias integrações adicionais com fontes autorizadas para ampliar a cobertura.
- **Não reproduz o relatório do radar do ChatGPT**: é um coletor autônomo que produz seu próprio e-mail. Mantenha o radar ChatGPT para pesquisa mais ampla, interpretação de anúncios e referências salariais.
- A fonte pode permitir vagas remotas que não aceitem candidatos no Brasil: validamos restrições geográficas informadas, mas isso não equivale à leitura jurídica de todos os requisitos.
- Não inventa **médias salariais**: só mostra salário divulgado pela fonte ou indica ausência de média verificada. A média por cargo requer integração adicional a benchmarks confiáveis.
- Não executa candidaturas; nomes de empresas e URLs são fornecidos pelos provedores.
- O repositório do perfil é **público**: `vistos.json` guarda apenas combinações de cargo e empresa, nunca senhas ou dados de candidatura.
- Se o Gmail exigir nova autorização ou bloquear SMTP, o workflow falhará e o histórico não avançará.

## Executar localmente

```bash
GMAIL_USER="seu_email" GMAIL_APP_PASSWORD="sua_senha_de_app" python radar_email/radar.py
```

Execute somente em ambiente privado e seguro. **Não compartilhe credenciais neste chat nem faça commit delas.**
