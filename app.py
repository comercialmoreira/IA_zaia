from flask import Flask, request, jsonify
import requests
import xmltodict

app = Flask(__name__)

# Rota principal para testar se o servidor está rodando
@app.route('/')
def home():
    return "Middleware de conversão XML para JSON está rodando!"

# Rota que converte XML para JSON
@app.route('/convert-xml', methods=['GET'])
def convert_xml():
    XML_URL = "https://restrito.casteldigital.com.br/vivareal_open/guilhermepilger-vivareal.xml?auth=gVQP3yQzqn"
    
    response = requests.get(XML_URL)
    if response.status_code == 200:
        data_dict = xmltodict.parse(response.text)
        return jsonify(data_dict)  # Retorna JSON

    return jsonify({"error": "Falha ao obter dados da API"}), response.status_code

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
