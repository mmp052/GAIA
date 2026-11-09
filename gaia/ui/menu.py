class Menu:
    def __init__(self):
        self._opcoes = {}

    def registrar(self, tecla, titulo, funcao):
        self._opcoes[str(tecla)] = (titulo, funcao)

    def obter(self, tecla):
        return self._opcoes[str(tecla)][1]

    def itens(self):
        return sorted(self._opcoes.items(), key=lambda kv: kv[0])
