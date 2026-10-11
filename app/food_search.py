"""Locally learned relevance for explicit BLS search selections."""
import json
from typing import Literal
from uuid import UUID
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

class Selection(BaseModel):
    id: UUID
    query: str = Field(min_length=1,max_length=200)
    lang: Literal['de','en']
    bls_code: str = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.query.strip(): raise ValueError('Search term required')
        return self

def term(query,normalize):
    return ' '.join(normalize(query).split())

def pattern(query):
    return '%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'

def search(db,normalize,q,lang,limit):
    query=term(q,normalize)
    if not query: raise HTTPException(422,'Search term required')
    with db() as c:
        rows=c.execute("""
            SELECT f.code,f.payload,COALESCE(s.hits,0) AS hits,COALESCE(s.last_selection,0) AS last_selection
            FROM foods f LEFT JOIN (
                SELECT code,COUNT(*) AS hits,MAX(rowid) AS last_selection
                FROM food_search_selections WHERE query=? AND lang=? GROUP BY code
            ) s ON s.code=f.code
            WHERE f.search LIKE ? ESCAPE '\\'
        """,(query,lang,pattern(query))).fetchall()
    ranked=[]
    for row in rows:
        food=json.loads(row['payload']);name=term(food['name_'+lang],normalize)
        # Personal choices rank first, then a predictable text relevance fallback.
        rank=(-row['hits'],-row['last_selection'],name!=query,not name.startswith(query),len(name),name,row['code'])
        ranked.append((rank,{'display_name':food['name_'+lang],**food}))
    return [food for _,food in sorted(ranked,key=lambda pair:pair[0])[:limit]]

def install(app,db,auth,normalize):
    @app.post('/food-search/selections',dependencies=[Depends(auth)])
    async def selected(body:Selection):
        query=term(body.query,normalize)
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            previous=c.execute('SELECT query,lang,code FROM food_search_selections WHERE id=?',(str(body.id),)).fetchone()
            if previous:
                if tuple(previous)!=(query,body.lang,body.bls_code):
                    raise HTTPException(409,'Selection ID already used')
                return {'learned':True}
            match=c.execute("SELECT code FROM foods WHERE code=? AND search LIKE ? ESCAPE '\\'",(body.bls_code,pattern(query))).fetchone()
            if not match: raise HTTPException(422,'Selected food does not match the search')
            c.execute('INSERT INTO food_search_selections(id,query,lang,code) VALUES(?,?,?,?)',(str(body.id),query,body.lang,body.bls_code))
        return {'learned':True}
