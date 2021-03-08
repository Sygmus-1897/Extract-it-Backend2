import praw

def getReddit():
    CONFIGS = {
        'client_id': "<clientId>",
        'client_secret': '<clientSecret>',
        'username': '<username>',
        'password': '<password>',
        'user_agent': '<userAgent>'
    }
    global reddit
    reddit = praw.Reddit(client_id=CONFIGS['client_id'], client_secret=CONFIGS['client_secret'], \
                         password=CONFIGS['password'], username=CONFIGS['username'], user_agent=CONFIGS['user_agent'])

    return reddit