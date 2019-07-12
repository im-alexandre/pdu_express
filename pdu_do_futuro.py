#!/usr/bin/env python3
# coding: utf-8

# importar bibliotecas necessárias
from datetime import datetime
import time
import sqlite3 as sql
import os
import smtplib
from email.message import EmailMessage
import paho.mqtt.client as mqtt  # ler e publicar tópicos mqtt
import serial  # comunicação USB

nome = "Járvis"

def dizer(fala):
    print(" -> " + fala + "\n")
    os.system("espeak -vpt-br -s 135 '%s'" % (fala))

dizer("Olá, eu sou o " + nome + ", atendente do PDU express!")
dizer("Antes de começarmos, preciso fazer alguns testes.")
time.sleep(1)

dizer("Conectando ao caixa.")
try:
    ENTRADA = serial.Serial('/dev/ttyACM0', 9600, timeout=0.2)
    """ conecta ao USB e,
    se não receber nada em 0.2s, passa direto"""
    ENTRADA.reset_input_buffer()
    # apaga o que já estava na serial antes de conectar
except:
    dizer("Caixa não encontrado.")

# variáveis com o endereço dos bancos de dados
banco_dados = os.path.join("/home/pi/share/.data_bases/pdu_express.db")

# conectar ao banco de dados
conn = sql.connect(banco_dados)

cur = conn.cursor()
# variável que acumula o valor da compra
TOTAL = 0
COMPRAS = {}


class Produtos():
    """ Classe que instancia produtos """
    global TOTAL

    def __init__(self, codigo):
        self.codigo = codigo
        cur.execute("SELECT descricao \
                    FROM produtos \
                    WHERE cod_prod = '%s'" % codigo)
        self.nome = cur.fetchone()[0]

        cur.execute("SELECT valor \
                              FROM produtos \
                              WHERE cod_prod = '%s'" % codigo)
        self.valor = cur.fetchone()[0]

        cur.execute("SELECT estoque \
                              FROM produtos \
                              WHERE cod_prod = '%s'" % codigo)
        conn.commit()
        self.estoque = cur.fetchone()[0]

    def registro(self):
        """Registra o produto"""
        global TOTAL
        global COMPRAS
        TOTAL += float(self.valor)
        dizer(self.nome)
        try:
            COMPRAS[self.codigo] += 1
        except:
            COMPRAS[self.codigo] = 1

        cur.execute("""update PRODUTOS
        set estoque = {0}-1
        where cod_prod='{1}'""".format(int(self.estoque), self.codigo))
        conn.commit()

class Oficiais():
    """ Classe para verificar oficiais """
    def __init__(self, codigo):
        self.codigo = codigo
        postos = {"Tenente":    ["CT", "1T", "2T"],
                  "Comandante": ["CMG", "CF", "CC"],
                  "Almirante":  ["CA", "VA", "AE"]}
        cur.execute("SELECT posto \
                              FROM OFICIAIS \
                              WHERE cod_cli = '%s'" % codigo)
        self.posto = cur.fetchone()[0]

        cur.execute("SELECT nip \
                              FROM OFICIAIS WHERE cod_cli = '%s'" % codigo)

        self.nip = cur.fetchone()[0]

        for x, y in postos.items():
            if self.posto in y:
                self.vocativo = x

        cur.execute("SELECT nome \
                              FROM OFICIAIS \
                              WHERE cod_cli = '%s'" % codigo)
        self.nome = cur.fetchone()[0]

        cur.execute("SELECT email \
        FROM OFICIAIS WHERE cod_cli = '%s'" % codigo)
        self.email = cur.fetchone()[0]

    def entrada(self):
        """Realiza as tarefas quando o oficial entrar"""
        CLIENT.publish("pduexpress/aut_entrada", "1")
        CLIENT.publish("pduexpress/iluminacao", "0", True)
        FALA = "Bem vindo, " + self.vocativo + " " + self.nome + \
            ", meu nome é " + nome + ", atendente do PDU express."
        dizer(FALA)
        hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO ACESSO VALUES(?, ?, ?)",
                    (self.nip, hora, '1'))
        conn.commit()


    def mandarEmail(self):
        global COMPRAS
        global TOTAL
        msg = EmailMessage()
        msg['To'] = [self.email]
        msg['Subject'] = 'PDU Express - relação de compras'
        msg['From'] = "xandao.labs@gmail.com"
        with open("email", "w") as email:
            email.write("Item" + 5 * "-" + "QTDE" + 5 * "- \n")

        cod_compra = datetime.now().strftime("%d%H%M")
        with open("email", "a") as email:
            for x, y in COMPRAS.items():
                produto = Produtos(x)
                email.writelines(produto.nome + 5 * "-" + str(y) + "\n")
                cur.execute("INSERT INTO COMPRA_ITEM VALUES(?, ?, ?)",
                            (cod_compra, produto.codigo, str(y)))

        conn.commit()

        cur.execute("INSERT INTO COMPRA VALUES(?, ?, ?)",
                    (cod_compra, self.nip, TOTAL))
        conn.commit()

        # with open("email", "a") as email:
        #     email.writelines("Total da compra" + str(TOTAL))
        with open("email", "r") as email:
            msg.set_content(email.read())
        s.sendmail("msg['From']", msg['To'], msg.as_string())
        TOTAL = 0
        os.system('rm email')

    def saida(self):
        """Realiza as tarefas referentes à saída"""
        FALA = "Até mais, " + self.vocativo + self.nome + \
               ", estou encaminhando a relação de compras para o seu e-mail. \
               Foi um prazer. Volte sempre!"
        CLIENT.publish("pduexpress/aut_saida", "1")
        CLIENT.publish("pduexpress/iluminacao", "1")
        self.mandarEmail()
        dizer(FALA)
        hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cur.execute("INSERT INTO ACESSO VALUES(?, ?, ?)",
                    (self.nip, hora, '0'))
        conn.commit()

def on_connect(CLIENT, userdata, flags, rc):
    """ O subscribe fica no on_connect pois, caso perca a conexão ele reconecta
    Quando usado o #, assina todos os tópicos que começam com 'acesso/' """
    CLIENT.subscribe("acesso/#")


def controle_acesso(msg):
    """ Lê o código recebido pelo MQTT e busca no DB se é um militar
    cadastrado"""
    global TOTAL
    cod = msg.payload.decode("utf-8")[1:]
    cod = cod.upper()
    print(cod)
    oficial = Oficiais(cod)
    # --- verifica se o código recebido é uma identidade
    if msg.topic == "acesso/entrada":
        oficial.entrada()
    elif msg.topic == "acesso/saida":
        oficial.saida()


def caixa():
    "Função de leitura dos cartões no leitor do caixa"
    global TOTAL
    com = ENTRADA.readline()[1:-1]
    # recebe os dados da porta serial (arduino + RFID)
    linha = com.decode("utf-8")     # traduz para string
    if linha != "":
        produto = Produtos(linha)
        produto.registro()


def on_message(CLIENT, userdata, msg):
    """ Callback responável por receber uma mensagem
    publicada no tópico acima"""
    controle_acesso(msg)

def avisoEstoque():
    cur.execute("SELECT descricao,estoque,nv_seg FROM PRODUTOS \
               WHERE estoque < nv_seg")
    lista = cur.fetchall()
    if lista != []:
        msg = EmailMessage()
        msg['To'] = ["email.exemplo"]
        msg['Subject'] = 'PDU Express - Estoque abaixo do nível de segurança'
        msg['From'] = "email@exemplo"
        with open("email.txt", "w") as e:
            e.writelines("O(s) seguintes itens estão abaixo do nível de segurança: \n \n")

        with open("email.txt", "a") as e:
            e.writelines("Descrição-----quantidade atual-----nível de segurança\n")
            for i in lista:
                e.writelines(str(i[0]) + 5 * "-" + str(i[1]) + 5 * "-" + str(i[2]) + "\n")

        with open("email.txt", "r") as email:
            msg.set_content(email.read())

        s.sendmail("msg['From']", msg['To'], msg.as_string())
        os.system('rm email.txt')
        cur.execute("update PRODUTOS \
        set estoque = nv_seg + 100 \
        WHERE estoque < nv_seg")
        conn.commit()

# Instanciando objetos MQTT
CLIENT = mqtt.Client()
CLIENT.on_connect = on_connect
CLIENT.on_message = on_message


# ---FUNÇÃO PRINCIPAL ---


# Conectando ao e-mail
dizer("Conectando ao servidor de e-mail")
s = smtplib.SMTP('smtp.gmail.com', 587)
s.starttls()
s.login('email@exemplo', 'SENHA')

# Conecta no MQTT Broker, no caso, o raspberry Pi rodando o "Mosquitto"
CLIENT.connect("localhost")
dizer("Conectando ao servidor de automação.")
dizer("testando porta de entrada")
time.sleep(0.5)
CLIENT.publish("pduexpress/aut_entrada", "1")
time.sleep(1)
dizer("testando porta de saída")
time.sleep(0.5)
CLIENT.publish("pduexpress/aut_saida", "1")
time.sleep(1)
dizer("testando iluminação")
time.sleep(1)
CLIENT.publish("pduexpress/iluminacao", "0")
time.sleep(1)
CLIENT.publish("pduexpress/iluminacao", "1")
time.sleep(1)
CLIENT.publish("pduexpress/iluminacao", "0")
time.sleep(1)
CLIENT.publish("pduexpress/iluminacao", "1")
time.sleep(0.5)
dizer("Ok, tudo pronto!")

while True:
    CLIENT.loop()   # chama a função on_message
    caixa()         # controla o "caixa" do PDU
    avisoEstoque()  # avisa sobre baixas de estoque
