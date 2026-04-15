from django.urls import path
from accounts.views import BrokerApplicationView, BrokerProfileView, index

urlpatterns = [
    path("broker-profile/", BrokerProfileView.as_view(), name="broker-profile"),
    path("broker-application/", BrokerApplicationView.as_view(), name="broker-application"),
    path("", index, name="index"),

]