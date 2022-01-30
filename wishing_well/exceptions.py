class AuthTokenExtractionError(Exception):
    pass

class EndpointError(Exception):
    pass

class RequestError(Exception):
    pass

class MissingAuthTokenError(Exception):
    pass

class LogNotFoundError(Exception):
    pass
