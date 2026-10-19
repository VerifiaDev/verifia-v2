"""Provider-independent failures containing only public, fixed messages."""


class UpstreamError(Exception):
    def __init__(self):
        super().__init__("Yapay zekâ servisine erişilirken bir hata oluştu.")


class InvalidModelResponse(UpstreamError):
    def __init__(self):
        Exception.__init__(self, "Yapay zekâ servisinin yanıtı işlenemedi.")


class UpstreamRateLimited(UpstreamError):
    def __init__(self):
        Exception.__init__(self, "Yapay zekâ servisinin kullanım sınırına ulaşıldı. Daha sonra yeniden deneyin.")


class UpstreamTimeout(UpstreamError):
    def __init__(self):
        Exception.__init__(self, "Yapay zekâ servisi zamanında yanıt vermedi.")
