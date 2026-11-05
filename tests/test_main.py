import base64
import json

import pytest

import main


def b64(texto):
    return base64.urlsafe_b64encode(texto.encode("utf-8")).decode()

# ============================================================
# extrair_email
# ============================================================


def test_extrair_email_com_formato_nome_e_email():
    assert main.extrair_email("João <Joao@EX.com>") == "joao@ex.com"


def test_extrair_email_sem_angulo():
    assert main.extrair_email("noangle@ex.com") == "noangle@ex.com"


def test_extrair_email_remove_espacos_e_minusculo():
    assert main.extrair_email("  PLAIN@EX.COM  ") == "plain@ex.com"


def test_extrair_email_vazio():
    assert main.extrair_email("  ") == ""


# ============================================================
# esta_bloqueado
# ============================================================


def test_esta_bloqueado_lista_vazia():
    assert main.esta_bloqueado("a@b.com", []) is False


def test_esta_bloqueado_lista_none():
    assert main.esta_bloqueado("a@b.com", None) is False


def test_esta_bloqueado_email_exato_case_insensitive():
    assert main.esta_bloqueado("A@B.COM", ["a@b.com"]) is True


def test_esta_bloqueado_dominio():
    assert main.esta_bloqueado("User <User@SPAM.com>", ["@spam.com"]) is True


def test_esta_bloqueado_dominio_nao_corresponde():
    assert main.esta_bloqueado("plain@ex.com", ["@spam.com"]) is False


def test_esta_bloqueado_ignora_itens_vazios():
    assert main.esta_bloqueado("a@b.com", ["", "  "]) is False


def test_esta_bloqueado_nao_bloqueado():
    assert main.esta_bloqueado("a@b.com", ["c@d.com"]) is False


# ============================================================
# Lista negra (arquivo)
# ============================================================


def test_carregar_lista_negra_sem_arquivo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main.carregar_lista_negra() == []


def test_carregar_lista_negra_corrompida(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "lista_negra.json").write_text("{invalido", encoding="utf-8")
    assert main.carregar_lista_negra() == []


def test_salvar_e_carregar_lista_negra(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lista = ["a@b.com", "@spam.com"]
    main.salvar_lista_negra(lista)
    assert main.carregar_lista_negra() == lista


def test_salvar_lista_negra_preserva_unicode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lista = ["usuário@ex.com"]
    main.salvar_lista_negra(lista)
    bruto = (tmp_path / "lista_negra.json").read_text(encoding="utf-8")
    assert "usuário@ex.com" in bruto
    assert main.carregar_lista_negra() == lista


def test_salvar_lista_negra_formato_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    main.salvar_lista_negra(["x@y.com"])
    dados = json.loads((tmp_path / "lista_negra.json").read_text(encoding="utf-8"))
    assert dados == ["x@y.com"]


# ============================================================
# obter_header
# ============================================================


def test_obter_header_case_insensitive():
    payload = {"headers": [{"name": "From", "value": "a@b.com"}]}
    assert main.obter_header(payload, "from") == "a@b.com"
    assert main.obter_header(payload, "FROM") == "a@b.com"


def test_obter_header_ausente_retorna_vazio():
    assert main.obter_header({}, "From") == ""
    assert main.obter_header({"headers": []}, "From") == ""


def test_obter_header_primeira_ocorrencia():
    payload = {
        "headers": [
            {"name": "Subject", "value": "Um"},
            {"name": "subject", "value": "Dois"},
        ]
    }
    assert main.obter_header(payload, "Subject") == "Um"


# ============================================================
# decodificar_base64url
# ============================================================


def test_decodificar_base64url_vazio():
    assert main.decodificar_base64url("") == ""
    assert main.decodificar_base64url(None) == ""


def test_decodificar_base64url_ascii():
    assert main.decodificar_base64url(b64("ola")) == "ola"


def test_decodificar_base64url_unicode_sem_padding():
    codificado = b64("olá mundo").rstrip("=")
    assert main.decodificar_base64url(codificado) == "olá mundo"


# ============================================================
# limpar_html
# ============================================================


def test_limpar_html_remove_tags():
    limpo = main.limpar_html("<p>Olá <b>mundo</b></p>")
    assert "Olá" in limpo
    assert "mundo" in limpo
    assert "<" not in limpo
    assert ">" not in limpo

def test_limpar_html_remove_script_e_style():
    limpo = main.limpar_html("<style>p{}</style>Olá<script>alert(1)</script> mundo")
    assert "alert" not in limpo
    assert "Olá" in limpo
    assert "mundo" in limpo


def test_limpar_html_entidades():
    limpo = main.limpar_html("Olá &amp; bem-vindo &lt;teste&gt;")
    assert "&amp;" not in limpo
    assert "Olá" in limpo


# ============================================================
# extrair_texto_email / _coletar_textos
# ============================================================


def test_coletar_textos_plain_e_html():
    payload = {
        "mimeType": "multipart/mixed",
        "body": {},
        "parts": [
            {"mimeType": "text/plain", "body": {"data": b64("texto plain")}},
            {"mimeType": "text/html", "body": {"data": b64("<p>texto html</p>")}},
        ],
    }
    plain, html_list = [], []
    main._coletar_textos(payload, plain, html_list)
    assert plain == ["texto plain"]
    assert html_list == ["<p>texto html</p>"]


def test_extrair_texto_email_plain_longo():
    msg = {
        "payload": {
            "mimeType": "text/plain",
            "body": {"data": b64("Olá mundo, este é um email de teste bem longo e completo.")},
        }
    }
    assert main.extrair_texto_email(msg) == "Olá mundo, este é um email de teste bem longo e completo."


def test_extrair_texto_email_html_quando_sem_plain():
    msg = {"payload": {"mimeType": "text/html", "body": {"data": b64("<p>Olá <b>mundo</b> teste</p>")}}}
    limpo = main.extrair_texto_email(msg)
    assert "Olá" in limpo
    assert "mundo" in limpo
    assert "<" not in limpo
    assert ">" not in limpo

def test_extrair_texto_email_fallback_html_quando_plain_curto():
    msg = {
        "payload": {
            "mimeType": "multipart/mixed",
            "body": {},
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64("curto")}},
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": b64(
                            "<p>Conteúdo html bem mais longo que cinquenta caracteres para fallback funcionar.</p>"
                        )
                    },
                },
            ],
        }
    }
    limpo = main.extrair_texto_email(msg)
    assert "Conteúdo html" in limpo


def test_extrair_texto_email_sem_payload():
    assert main.extrair_texto_email({}) == ""


# ============================================================
# limpar_texto
# ============================================================


def test_limpar_texto_remove_urls():
    assert main.limpar_texto("Olá https://example.com fim") == "Olá fim"


def test_limpar_texto_remove_linhas_sem_letras():
    assert main.limpar_texto("Texto qualquer\n12345\nOutra linha válida") == "Texto qualquer Outra linha válida"


def test_limpar_texto_corta_citacao_em():
    texto = "Primeira linha\nsegunda linha\nEm 2024, o usuário escreveu:\nconteúdo citado"
    assert main.limpar_texto(texto) == "Primeira linha segunda linha"


def test_limpar_texto_corta_on_wrote():
    texto = "Resposta\nOn Mon, 1 Jan 2024 user wrote:\ncitação"
    assert main.limpar_texto(texto) == "Resposta"


# ============================================================
# detectar_idioma
# ============================================================


def test_detectar_idioma_portugues():
    texto = "Olá, você é de que lugar? Obrigado por tudo que você fez para nós."
    assert main.detectar_idioma(texto) == "portuguese"


def test_detectar_idioma_ingles():
    texto = "Hello, you are welcome. Thank you for everything that you did for us."
    assert main.detectar_idioma(texto) == "english"


def test_detectar_idioma_vazio_default_portugues():
    assert main.detectar_idioma("") == "portuguese"


# ============================================================
# gerar_resumo_extrativo
# ============================================================


def test_gerar_resumo_texto_curto_retorna_como_esta():
    resumo, idioma = main.gerar_resumo_extrativo("curto")
    assert resumo == "curto"
    assert idioma == "portuguese"


def test_gerar_resumo_vazio():
    resumo, _ = main.gerar_resumo_extrativo("")
    assert resumo == ""


def test_gerar_resumo_texto_longa_respeita_n_frases():
    texto = (
        "Este é o primeiro email importante sobre o projeto GAIA. "
        "O segundo email fala sobre o prazo do projeto GAIA. "
        "O terceiro email menciona reunião importante com a equipe. "
        "O quarto email é apenas um aviso geral sobre manutenção do sistema. "
        "O quinto email contém detalhes sobre o orçamento do projeto."
    )
    resumo, idioma = main.gerar_resumo_extrativo(texto)
    assert idioma == "portuguese"
    assert "projeto" in resumo.lower()
    # No máximo 3 frases no resumo
    assert resumo.count(".") <= 3


def test_gerar_resumo_preserva_ordem_original():
    texto = (
        "Este é o primeiro email importante sobre o projeto GAIA. "
        "O segundo email fala sobre o prazo do projeto GAIA. "
        "O terceiro email menciona reunião importante com a equipe. "
        "O quarto email é apenas um aviso geral sobre manutenção do sistema. "
        "O quinto email contém detalhes sobre o orçamento do projeto."
    )
    resumo, _ = main.gerar_resumo_extrativo(texto, n_frases=2)
    assert resumo.count(".") <= 2


def test_gerar_resumo_trunca_texto_sem_frases_validas():
    texto = "palavra " * 400
    resumo, _ = main.gerar_resumo_extrativo(texto)
    assert len(resumo) == 500


# ============================================================
# link_email
# ============================================================


def test_link_email_usa_thread_id():
    assert main.link_email("msg1", "thread1") == "https://mail.google.com/mail/u/0/#inbox/thread1"


def test_link_email_usa_msg_id_quando_sem_thread():
    assert main.link_email("msg1") == "https://mail.google.com/mail/u/0/#inbox/msg1"


def test_link_email_thread_vazio_usa_msg_id():
    assert main.link_email("msg1", None) == "https://mail.google.com/mail/u/0/#inbox/msg1"


# ============================================================
# resumir_emails (caminho de erro sem credenciais)
# ============================================================


def test_resumir_emails_sem_credenciais_retorna_sem_erro(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # Sem token.json e sem credentials.json -> não deve levantar exceção
    main.resumir_emails()
    captured = capsys.readouterr()
    assert "credentials.json" in captured.out.lower()
