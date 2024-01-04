from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from mnemonic import Mnemonic
from eth_account import Account
from eth_keys import keys
from eth_utils import to_checksum_address, to_hex
import bip32utils
from web3 import Web3, HTTPProvider

app = Flask(__name__)
app.config[
    "SQLALCHEMY_DATABASE_URI"
] = "postgresql://postgres:12345@localhost:5432/passwords"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class StringModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(255), nullable=False)


# Endpoint to store a string in the database with GET method
@app.route("/store_string", methods=["GET"])
def store_string():
    value = request.args.get("value")

    if not value:
        return jsonify({"error": "Missing value parameter"}), 400

    new_string = StringModel(value=value)

    try:
        with app.app_context():  # Enter the application context
            db.create_all()  # Create tables if they don't exist
            db.session.add(new_string)
            db.session.commit()
        return jsonify({"message": "String stored successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.session.close()


# Endpoint to get all strings from the database
@app.route("/get_all_strings", methods=["GET"])
def get_all_strings():
    strings = StringModel.query.all()
    string_list = [{"id": string.id, "value": string.value} for string in strings]
    return jsonify({"strings": string_list})


# Endpoint to get a string by its ID
@app.route("/get_string/<int:string_id>", methods=["GET"])
def get_string_by_id(string_id):
    string = StringModel.query.get(string_id)

    if not string:
        return jsonify({"error": "String not found"}), 404

    return jsonify({"id": string.id, "value": string.value})


# Endpoint to transfer coin
@app.route("/transfer_coin", methods=["POST"])
def transfer_coin():
    data = request.json
    secret_key = data.get("secret_key")
    receiver_address = data.get("receiver_address")

    # Validate and convert the address to checksum format
    try:
        receiver_address = to_checksum_address(receiver_address)
    except ValueError:
        return jsonify({"error": "Invalid receiver address"}), 400

    if not secret_key or not receiver_address:
        return jsonify({"error": "Missing secret key or receiver address"}), 400

    # Generate a seed from the mnemonic
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(secret_key)

    # Derive the private key
    hdp = bip32utils.BIP32_HARDEN
    path = [44 + hdp, 60 + hdp, 0 + hdp, 0, 0]
    key = bip32utils.BIP32Key.fromEntropy(seed)
    for index in path:
        key = key.ChildKey(index)

    private_key_bytes = key.PrivateKey()
    private_key = keys.PrivateKey(private_key_bytes)

    # Derive the public address from the private key
    public_key = private_key.public_key
    address = to_checksum_address(public_key.to_address())

    # Connect to BSC node
    w3 = Web3(HTTPProvider("https://bsc-dataseed.binance.org/"))
    if not w3.is_connected():
        return jsonify({"error": "Failed to connect to the BSC node"}), 500

    # Set transaction details
    nonce = w3.eth.get_transaction_count(address)
    gas_price = w3.eth.gas_price
    gas_limit = 21000  # Standard gas limit for BNB transfer
    value = w3.to_wei(0.005, "ether")  # Amount of BNB to send

    transaction = {
        "to": receiver_address,
        "value": value,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "nonce": nonce,
        "chainId": 56,  # BSC Mainnet chain ID
    }

    # Sign the transaction
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key.to_hex())

    # Send the transaction (uncomment to enable real transaction)
    # txn_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    # return jsonify({"message": f"Transaction hash: {to_hex(txn_hash)}"}), 200
    return jsonify({"message": "Transaction is successful"}), 200


if __name__ == "__main__":
    app.run(debug=True)
