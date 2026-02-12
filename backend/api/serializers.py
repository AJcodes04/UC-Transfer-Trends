from rest_framework import serializers
from .models import TransferData


class TransferDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferData
        fields = '__all__'
