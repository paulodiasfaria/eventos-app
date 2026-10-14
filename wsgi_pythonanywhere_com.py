"""
WSGI config para PythonAnywhere.

Na PythonAnywhere, vai ao separador "Web" -> na secção "Code" ->
"WSGI configuration file" (algo como /var/www/paulodiasfaria_pythonanywhere_com_wsgi.py)
e substitui o conteudo por ISTO (ajusta o caminho se o teu projeto estiver noutro sitio).
"""
import sys
import os

project_home = '/home/paulodiasfaria/eventos-app'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ['EVENTOS_DB_PATH'] = '/home/paulodiasfaria/eventos-app/eventos.db'
os.environ['EVENTOS_API_KEY'] = 'DEFINE-UMA-CHAVE-SECRETA-AQUI'

from app import app as application  # noqa
