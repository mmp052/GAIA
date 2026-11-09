import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from oauthlib.oauth2.rfc6749.errors import AccessDeniedError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]


def obter_credenciais(console=None, token_path="token.json", credentials_path="credentials.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.path.exists(token_path):
                try:
                    os.remove(token_path)
                except OSError:
                    pass
            if not os.path.exists(credentials_path):
                if console is not None:
                    console.print("[red]ERRO: credentials.json não encontrado.[/red]")
                    console.print("Baixe no Google Cloud Console (OAuth Client > Desktop) e salve como credentials.json")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            try:
                creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="Abra {url} no navegador e clique em Permitir.", timeout_seconds=120)
            except AccessDeniedError as e:
                if console is not None:
                    console.print("\n[red]❌ Acesso negado no Google (access_denied).[/red]")
                    console.print("   → Na tela de consentimento, clique em 'Permitir' / 'Continuar' e autorize os escopos do Gmail.")
                    console.print("   → Se aparecer 'aplicativo não verificado', clique em 'Avançado' > 'Ir para o projeto (não seguro)'.")
                    console.print("   → Depois rode novamente a opção 1.")
                    console.print(f"   Detalhe: {e}")
                return None
            except KeyboardInterrupt:
                if console is not None:
                    console.print("\nOperação cancelada.")
                return None
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds
