from .extensions import *

learnMore_auth = Blueprint('learnMore_auth', __name__)

@learnMore_auth.route('/learnMoreAqi', methods=['GET'])
def learnMore():
    return render_template('auth/learnMore.html')