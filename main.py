import pyfiglet

# Usando figlet_format
ascii_arte = pyfiglet.figlet_format("GAIA", font="banner")
print(ascii_arte)

print("Digite a opção se quiser rodar a rotina descrita:")
print("1 - Resumidor de Emails")

while True:
    opcao = input()
