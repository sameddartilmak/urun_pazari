# /run.py

from app import create_app, db
# Modellerimizi migrate komutunun görebilmesi için buraya import ediyoruz
from app.models import User, Product, Listing, Transaction, SwapOffer

app = create_app()

# 'flask shell' ve 'flask db' komutları için context
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Product': Product, 
        'Listing': Listing,
        'Transaction': Transaction,
        'SwapOffer': SwapOffer
    }

if __name__ == '__main__':
    app.run(debug=True)