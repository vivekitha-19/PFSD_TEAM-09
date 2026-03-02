import graphene
from graphene_django import DjangoObjectType
from advisory.models import Crop, Disease

class CropType(DjangoObjectType):
    class Meta:
        model = Crop

class DiseaseType(DjangoObjectType):
    class Meta:
        model = Disease

class Query(graphene.ObjectType):
    crops = graphene.List(CropType)
    diseases = graphene.List(DiseaseType, crop_id=graphene.Int())

    def resolve_crops(self, info):
        return Crop.objects.all()

    def resolve_diseases(self, info, crop_id):
        return Disease.objects.filter(crop_id=crop_id)

schema = graphene.Schema(query=Query)