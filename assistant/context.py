from django.conf import settings


def company(request):
    return {"company_name": settings.COMPANY_NAME}
