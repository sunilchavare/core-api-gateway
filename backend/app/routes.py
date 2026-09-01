import os
from dotenv import load_dotenv

load_dotenv()

DOWNSTREAM_SERVICES= {
    "hello" : os.getenv("DOWNSTREAM_HELLO_URL")
}



