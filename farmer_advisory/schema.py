"""
Root GraphQL Schema - Farmer Advisory System
Combines all app-level schemas
"""
import graphene
from advisory.schema import Query as AdvisoryQuery, Mutation as AdvisoryMutation


class Query(AdvisoryQuery, graphene.ObjectType):
    pass


class Mutation(AdvisoryMutation, graphene.ObjectType):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
