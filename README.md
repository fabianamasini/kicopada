# Kicopada - Sistema de Bolão de Futebol

## Sobre o projeto
O Kicopada nasceu para gerenciar o bolão da copa com meus amigos. A ideia é criar um ambiente competitivo onde todo mundo pode dar seus palpites e subir no ranking, com um sistema de pontos e Odds.

## Especificações técnicas
- Desenvolvido em Python 3 e Flask
- SQLAlchemy (SQLite local e PostgreSQL na cloud)

## Get started
1. Instale as dependências que estão no arquivo ``requirements.txt``.
2. Execute ``python3 app.py``.
3. Na primeira vez, o sistema cria o banco e o usuário admin para você automaticamente.

## Variáveis de ambiente
```
SQLALCHEMY_DATABASE_URI = URL da base de dados
SECRET_KEY = Chave secreta aleatória
ADMIN_USER = Nome de usuário admin
ADMIN_PASSWORD = Senha de admin
```
