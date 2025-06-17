from fastapi import FastAPI
app = FastAPI()
@app.get('/docs')
def read_docs(): return {'message': 'Swagger UI'}