# Scripts de Seed do Banco de Dados

Este diretório contém scripts para gerenciar dados de teste na aplicação Kicopada.

## 📋 Scripts Disponíveis

### 1. `seed.py` (na raiz)
Cria um conjunto padrão de dados mockados realistas.

```bash
python seed.py
```

**O que é criado:**
- 5 usuários de teste
- 8 times de futebol
- 5 partidas futuras
- Odds e palpites variados

**Vantagens:**
- ✅ Rápido
- ✅ Não cria duplicatas
- ✅ Dados realistas
- ✅ Perfeito para testes manuais

---

### 2. `scripts/reset_db.py`
Limpa completamente o banco de dados (remove todas as tabelas).

```bash
python scripts/reset_db.py
```

**Cuidado:** Isso delete todos os dados! Use antes de fazer seed.

**Fluxo típico:**
```bash
python scripts/reset_db.py  # Limpa
python seed.py              # Popula com dados padrão
```

---

### 3. `scripts/seed_random.py`
Gera dados aleatórios em grande volume. Útil para testes de performance.

```bash
python scripts/seed_random.py
```

**Interativo:**
- Pergunta quantos usuários criar
- Pergunta quantas partidas criar

**Exemplo:**
```bash
$ python scripts/seed_random.py
Quantos usuários criar? (padrão: 50): 100
Quantas partidas criar? (padrão: 20): 30
```

---

## 🔑 Credenciais de Teste

Após rodar `python seed.py`, você pode fazer login com:

| Usuário | Senha |
|---------|-------|
| alice   | senha123 |
| bob     | senha123 |
| carlos  | senha123 |
| diana   | senha123 |
| eva     | senha123 |

---

## 🚀 Uso Recomendado

### Para testes simples:
```bash
python seed.py
```

### Para resetar e recriar:
```bash
python scripts/reset_db.py
python seed.py
```

### Para testes de performance:
```bash
python scripts/reset_db.py
python scripts/seed_random.py
```

---

## ⚙️ Estrutura de Dados

### Users
- `id`: identificador único
- `username`: nome do usuário
- `password_hash`: senha hasheada (werkzeug)
- `is_admin`: flag de administrador
- `points`: pontos acumulados

### Teams
- `id`: identificador único
- `name`: nome do time
- `group`: grupo da fase
- `points`: pontos no campeonato
- `disqualified`: eliminado?

### Matches
- `id`: identificador único
- `team_a`, `team_b`: times
- `date`: data/hora (ISO format)
- `round`: fase do campeonato
- `score_a`, `score_b`: placar (se finalizado)
- `is_knockout`: é mata-mata?

### Guesses (Palpites)
- `id`: identificador único
- `user_id`: usuário que fez o palpite
- `match_id`: partida
- `pred_a`, `pred_b`: palpite de placar
- `is_knockout`: é mata-mata?

### Odds
- `id`: identificador único
- `match_id`: partida
- `team_a_odds`, `team_b_odds`: odds de vitória
- `draw_odds`: odds de empate

---

## 💡 Dicas

- Os dados são criados apenas se não existirem (seguro rodar múltiplas vezes)
- As datas das partidas são sempre futuras (a partir de amanhã)
- Cada execução do `seed.py` adiciona novos dados sem duplicar
- Para limpar dados antigos, use `reset_db.py` antes
