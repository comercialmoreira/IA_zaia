from flask import Flask, request, jsonify
import requests
import xmltodict

app = Flask(__name__)

# URL da API XML original
XML_URL = "https://restrito.casteldigital.com.br/vivareal_open/guilhermepilger-vivareal.xml?auth=gVQP3yQzqn"

@app.route('/')
def home():
    return "Middleware de conversão XML para JSON com filtros está rodando!"

@app.route('/convert-xml', methods=['GET'])
def convert_xml():
    response = requests.get(XML_URL)

    if response.status_code == 200:
        data_dict = xmltodict.parse(response.text)

        if "ListingDataFeed" in data_dict and "Listings" in data_dict["ListingDataFeed"]:
            listings = data_dict["ListingDataFeed"]["Listings"]["Listing"]

            # Se houver apenas um imóvel, transformar em lista para evitar erros
            if isinstance(listings, dict):
                listings = [listings]

            # Pegar parâmetros da URL preenchidos pela ZAIA
            nome_imovel = request.args.get("nome_imovel", "").lower()
            cidade = request.args.get("cidade", "").lower()
            preco_min = float(request.args.get("preco_min", 0))
            preco_max = float(request.args.get("preco_max", float('inf')))
            finalidade = request.args.get("finalidade", "").lower()
            desejos = request.args.get("desejos", "").lower()

            # Aplicar filtros nos imóveis
            listings_filtrados = []
            for listing in listings:
                detalhes = listing.get("Details", {})
                localizacao = listing.get("Location", {})
                preco_info = detalhes.get("ListPrice", {}).get("#text", "0")
                nome = detalhes.get("Tipologia", "").lower()  # Pegando o nome do imóvel

                # Converter preço para número
                try:
                    preco = float(preco_info)
                except ValueError:
                    preco = 0  

                # Filtrar por nome do imóvel (se fornecido)
                if nome_imovel and nome_imovel not in nome:
                    continue

                # Filtrar por cidade
                if cidade and localizacao.get("City", "").lower() != cidade:
                    continue

                # Filtrar por preço
                if not (preco_min <= preco <= preco_max):
                    continue

                # Filtrar por finalidade (venda, aluguel)
                tipo_finalidade = detalhes.get("PropertyType", "").lower()
                if finalidade and finalidade not in tipo_finalidade:
                    continue

                # Filtrar por desejos (ex: piscina, vista para o mar)
                features = detalhes.get("Features", {}).get("Feature", [])
                if isinstance(features, str):
                    features = [features]  # Se for string única, transformar em lista

                if desejos:
                    lista_desejos = [d.strip().lower() for d in desejos.split(",")]
                    if not any(d in [f.lower() for f in features] for d in lista_desejos):
                        continue

                listings_filtrados.append(listing)

            # Retornar resposta JSON apenas com imóveis filtrados
            return jsonify({"Listings": listings_filtrados})

    return jsonify({"error": "Falha ao obter dados da API"}), response.status_code

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
