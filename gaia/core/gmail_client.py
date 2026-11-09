def listar_nao_lidos(service, consulta, max_paginas=20):
    lista = []
    params = {"userId": "me", "labelIds": ["UNREAD"], "q": consulta}
    for _ in range(max_paginas):
        results = service.users().messages().list(**params).execute()
        lista += results.get("messages") or []
        token = results.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
    return lista


def obter_mensagem(service, msg_id):
    return service.users().messages().get(userId="me", id=msg_id).execute()


def marcar_como_lida(service, msg_id):
    service.users().messages().modify(
        userId="me",
        id=msg_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def buscar_dia_mais_recente(service, hoje, dias=30, on_progress=None):
    from datetime import timedelta

    lista = []
    busca = []
    data_alvo = None
    for dias_atras in range(dias):
        dia = hoje - timedelta(days=dias_atras)
        dia_str = dia.strftime("%Y/%m/%d")
        dia_anterior = (dia - timedelta(days=1)).strftime("%Y/%m/%d")
        dia_seguinte = (dia + timedelta(days=1)).strftime("%Y/%m/%d")
        consulta = f"after:{dia_anterior} before:{dia_seguinte}"
        achados = listar_nao_lidos(service, consulta)
        busca.append((dia_str, len(achados)))
        if on_progress is not None:
            on_progress(dia_str, len(achados), dias_atras + 1, dias)
        if achados:
            data_alvo = dia_str
            lista = achados
            break
    return data_alvo, lista, busca


def buscar_ultimas_24h(service, agora, horas=24, on_progress=None):
    from datetime import timedelta

    if agora.tzinfo is None:
        from datetime import timezone

        agora = agora.replace(tzinfo=timezone.utc)
    epoch = int((agora - timedelta(hours=horas)).timestamp())
    consulta = f"after:{epoch}"
    achados = listar_nao_lidos(service, consulta)
    dia_str = agora.strftime("%Y/%m/%d")
    busca = [(dia_str, len(achados))]
    if on_progress is not None:
        on_progress(dia_str, len(achados), 1, 1)
    data_alvo = dia_str if achados else None
    return data_alvo, achados, busca
