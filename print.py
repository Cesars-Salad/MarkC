import pyautogui
import time
import os

# Diretório onde as imagens serão salvas
pasta_destino = "capturas_de_tela"
os.makedirs(pasta_destino, exist_ok=True)  # Cria a pasta, se não existir

intervalo = 15  # Tempo em segundos entre as capturas

try:
    while True:
        # Captura da tela
        screenshot = pyautogui.screenshot()
        # Nome do arquivo com timestamp
        nome_arquivo = time.strftime("%Y-%m-%d_%H-%M-%S") + ".png"
        caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
        # Salva a captura
        screenshot.save(caminho_arquivo)
        print(f"Captura salva: {caminho_arquivo}")
        # Aguarda o próximo intervalo
        time.sleep(intervalo)
except KeyboardInterrupt:
    print("Script interrompido pelo usuário.")