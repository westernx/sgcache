import datetime
import sqlalchemy as sa

'''
{
    "fields": [
        {
            "field_name": "key", 
            "value": "value"
        }
    ], 
    "return_fields": [
        "id"
    ], 
    "type": "Test"
}
'''

class CreateHandler(object):

    def __init__(self, request, allow_id=False):

        self.request = request
        

        self.entity_type_name = request['type']
        self.data = {x['field_name']: x['value'] for x in request['fields']}
        self.return_fields = request['return_fields']

        self.entity_exists = None
        self.entity_id = self.data.get('id') # this is for field.prepare_upsert
        if self.entity_id and not allow_id:
            raise ValueError('cannot specify ID for create')

        self.before_query = []
        self.after_query = []

    def __call__(self, schema, con=None, extra=None):

        query_params = (extra or {}).copy()
        query_params['_active'] = True
        query_params['_cache_created_at'] = query_params['_cache_updated_at'] = datetime.datetime.utcnow()


        for field_name, field in schema[self.entity_type_name].fields.iteritems():
            value = self.data.get(field_name)
            if value is not None:
                field_params = field.prepare_upsert(self, value)
                if field_params:
                    query_params.update(field_params)

        con_given = con is not None
        con = con or schema.db.begin()

        try:

            table = schema[self.entity_type_name].table

            if self.entity_id:
                self.entity_exists = list(con.execute(table.select(table.c.id).where(table.c.id == self.entity_id).limit(1)))

            for func in self.before_query:
                func(con)

            if self.entity_exists:
                # these are only for creation
                del query_params['id']
                del query_params['_active']
                del query_params['_cache_created_at']
                con.execute(table.update().where(table.c.id == self.entity_id), **query_params)

            else:
                res = con.execute(table.insert(), **query_params)
                self.entity_id = self.entity_id or res.inserted_primary_key[0]

            for func in self.after_query:
                func(con)

            return {'type': self.entity_type_name, 'id': self.entity_id}

        except:
            if not con_given:
                con.rollback()
            raise
        else:
            if not con_given:
                con.commit()

