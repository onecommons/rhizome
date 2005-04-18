'''
    Schema support for RxPath, including an implementation of RDF Schema.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''
import StringIO, copy
from rx import utils
from Ft.Rdf import OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL
from Ft.Rdf import BNODE_BASE, BNODE_BASE_LEN,RDF_MS_BASE,RDF_SCHEMA_BASE
from Ft.Rdf.Statement import Statement

class BaseSchema(object):
    '''
    A "null" schema that does nothing. Illustrates the minimum
    interfaces that must be implemented.
    '''
    
    def isCompatibleType(self, testType, wantType):
        '''
        Returns whether or not the given type is compatible with
        a second type (e.g. equivalent to or a subclass of the second type)
        The given type may end in a "*", indicating a wild card.
        '''
        if wantType[-1] == '*':
            return testType.startswith(wantType[:-1])
        else:
            return testType == wantType
                         
    def isCompatibleProperty(self, testProp, wantProp):
        '''
        Returns whether or not the given property is compatible with
        a second property (e.g. equivalent to or a subproperty of the second type)
        The given property may end in a "*", indicating a wild card.
        '''        
        if wantProp[-1] == '*':
            return testProp.startswith(wantProp[:-1])
        else:
            return testProp == wantProp

    def findStatements(self, uri, explicitStmts):
        '''
        Return a list of inferred statements about the given resource
        based on the schema. A list of statements explicitly found in the model
        that the resource is the subject of may be given.
        '''
        return []
       
    def addToSchema(self, stmts): pass
    def removeFromSchema(self, stmts): pass
    
    def commit(self, **kw): pass
    def rollback(self): pass

class RDFSSchema(BaseSchema):
    '''
    This is a temporary approach that provides partial support of RDF Schema.

    It does the following:

    * Keeps track of subclasses and subproperties used by resource and predicate element name tests.
    * infers a resource is a rdf:Property or a rdfs:Class if it appears as
      either a predicate or as the object of a rdf:type statement
    ** adds rdf:type statements for those resources if no rdf:type statement is present.
    
    When the DOM is first initialized we add all inferred resources into the DOM,
    so that resources don't appear to be added non-deterministically
    based on which nodes in the DOM were accessed. (Doing so would break
    diffing and merging models, for example).
    However inferred statements (via findStatements) are only added when
    examining the resource. This is OK because it is basically deterministic
    as you always have to navigate through the node to see those statements.
    
    Todo: This doesn't support type inference based on rdfs:range or rdfs:domain.
    Todo: we don't fully support subproperties of rdf:type
    '''
    SUBPROPOF = u'http://www.w3.org/2000/01/rdf-schema#subPropertyOf'
    SUBCLASSOF = u'http://www.w3.org/2000/01/rdf-schema#subClassOf'

    #NTriples version of http://www.w3.org/2000/01/rdf-schema
    schemaTriples = r'''<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#comment> "The subject is a subproperty of a property." .
<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#label> "subPropertyOf" .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema#comment> "Further information about the subject resource." .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema#label> "seeAlso" .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/2000/01/rdf-schema#comment> "A member of the subject resource." .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#member> <http://www.w3.org/2000/01/rdf-schema#label> "member" .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/2000/01/rdf-schema#comment> "A description of the subject resource." .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Literal> .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#comment> <http://www.w3.org/2000/01/rdf-schema#label> "comment" .
<http://www.w3.org/2000/01/rdf-schema#> <http://www.w3.org/2000/01/rdf-schema#seeAlso> <http://www.w3.org/2000/01/rdf-schema-more> .
<http://www.w3.org/2000/01/rdf-schema#> <http://purl.org/dc/elements/1.1/title> "The RDF Schema vocabulary (RDFS)" .
<http://www.w3.org/2000/01/rdf-schema#> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Ontology> .
<http://www.w3.org/2000/01/rdf-schema#Datatype> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#Datatype> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Datatype> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Datatype> <http://www.w3.org/2000/01/rdf-schema#label> "Datatype" .
<http://www.w3.org/2000/01/rdf-schema#Datatype> <http://www.w3.org/2000/01/rdf-schema#comment> "The class of RDF datatypes." .
<http://www.w3.org/2000/01/rdf-schema#ContainerMembershipProperty> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#ContainerMembershipProperty> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#ContainerMembershipProperty> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#ContainerMembershipProperty> <http://www.w3.org/2000/01/rdf-schema#label> "ContainerMembershipProperty" .
<http://www.w3.org/2000/01/rdf-schema#ContainerMembershipProperty> <http://www.w3.org/2000/01/rdf-schema#comment> "The class of container membership properties, rdf:_1, rdf:_2, ...,\n                    all of which are sub-properties of 'member'." .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://www.w3.org/2000/01/rdf-schema#seeAlso> .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#comment> "The defininition of the subject resource." .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#label> "isDefinedBy" .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#comment> "The subject is a subclass of a class." .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#label> "subClassOf" .
<http://www.w3.org/2000/01/rdf-schema#Resource> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#Resource> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Resource> <http://www.w3.org/2000/01/rdf-schema#label> "Resource" .
<http://www.w3.org/2000/01/rdf-schema#Resource> <http://www.w3.org/2000/01/rdf-schema#comment> "The class resource, everything." .
<http://www.w3.org/2000/01/rdf-schema#Container> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#Container> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#Container> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Container> <http://www.w3.org/2000/01/rdf-schema#label> "Container" .
<http://www.w3.org/2000/01/rdf-schema#Container> <http://www.w3.org/2000/01/rdf-schema#comment> "The class of RDF containers." .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#comment> "A range of the subject property." .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#label> "range" .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#comment> "A domain of the subject property." .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#label> "domain" .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#Property> .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/2000/01/rdf-schema#comment> "A human-readable name for the subject." .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/2000/01/rdf-schema#range> <http://www.w3.org/2000/01/rdf-schema#Literal> .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/2000/01/rdf-schema#domain> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#label> <http://www.w3.org/2000/01/rdf-schema#label> "label" .
<http://www.w3.org/2000/01/rdf-schema#Class> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#Class> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#Class> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Class> <http://www.w3.org/2000/01/rdf-schema#label> "Class" .
<http://www.w3.org/2000/01/rdf-schema#Class> <http://www.w3.org/2000/01/rdf-schema#comment> "The class of classes." .
<http://www.w3.org/2000/01/rdf-schema#Literal> <http://www.w3.org/2000/01/rdf-schema#isDefinedBy> <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.w3.org/2000/01/rdf-schema#Literal> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <http://www.w3.org/2000/01/rdf-schema#Resource> .
<http://www.w3.org/2000/01/rdf-schema#Literal> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2000/01/rdf-schema#Class> .
<http://www.w3.org/2000/01/rdf-schema#Literal> <http://www.w3.org/2000/01/rdf-schema#label> "Literal" .
<http://www.w3.org/2000/01/rdf-schema#Literal> <http://www.w3.org/2000/01/rdf-schema#comment> "The class of literal values, eg. textual strings and integers." .
'''
    rdfSchema = [Statement(unicode(stmt[0]), unicode(stmt[1]), unicode(stmt[2]),
       objectType=unicode(stmt[3])) for stmt in utils.parseTriples(StringIO.StringIO(schemaTriples))]
    
    #statements about RDF resources are missing from the RDFS schema
    rdfAdditions = [Statement(x[0], x[1], x[2], objectType=OBJECT_TYPE_RESOURCE)
        for x in [
    (RDF_MS_BASE+u'Alt', SUBCLASSOF, RDF_SCHEMA_BASE+u'Container'),
    (RDF_MS_BASE+u'Bag', SUBCLASSOF, RDF_SCHEMA_BASE+u'Container'),
    (RDF_MS_BASE+u'Seq', SUBCLASSOF, RDF_SCHEMA_BASE+u'Container'),
    (RDF_MS_BASE+u'XMLLiteral', SUBCLASSOF, RDF_SCHEMA_BASE+u'Literal'),]
    ]
    
    requiredProperties = [RDF_MS_BASE+u'type']
    requiredClasses = [RDF_MS_BASE+u'Property', RDF_SCHEMA_BASE+u'Class']

    inTransaction = False
        
    def __init__(self, stmts = None, autocommit=False):
        #dictionary of type : ancestors (including self)
        self.supertypes = {}
        self.superproperties = {}

        #dictionary of type : descendants (including self)
        self.subtypes = {}
        self.subproperties = {} 

        self.subClassPreds = [self.SUBCLASSOF]
        self.subPropPreds =  [self.SUBPROPOF]
        self.typePreds =     [RDF_MS_BASE+u'type']
        
        for predicate in self.requiredProperties:
            self.subproperties.setdefault(predicate, [predicate])
            self.superproperties.setdefault(predicate, [predicate])
        for subject in self.requiredClasses:
            self.subtypes.setdefault(subject, [subject]) 
            self.supertypes.setdefault(subject, [subject])

        self.currentSubProperties = self.subproperties
        self.currentSubTypes = self.subtypes
        self.currentSuperProperties = self.superproperties
        self.currentSuperTypes = self.supertypes

        self.autocommit = True #to disable _beginTxn() during init
        self.addToSchema(self.rdfAdditions)
        self.addToSchema(self.rdfSchema)
        if stmts:
            self.addToSchema(stmts)
        self.autocommit = autocommit

    def isCompatibleType(self, testType, wantType):
        '''
        Is the given testType resource compatible with (equivalent to or a subtype of) the specified wantType?
        wantType can end in a * (to support the namespace:* node test in RxPath)
        '''
        if wantType == RDF_SCHEMA_BASE+'Resource': 
            return True
        return self._testCompatibility(self.currentSubTypes, testType, wantType)
    
    def isCompatibleProperty(self, testProp, wantProp):
        '''
        Is the given propery compatible with (equivalent to or a subpropery of) the specified property?
        wantProp can end in a * (to support the namespace:* node test in RxPath)
        '''
        return self._testCompatibility(self.currentSubProperties, testProp, wantProp)
    
    def _testCompatibility(self, map, testType, wantType):        
        #do the exact match test first in case we're calling this before we've completed setting up the schema            
        if testType == wantType:
            return True

        if wantType[-1] == '*':
            if testType.startswith(wantType[:-1]):
                return True
            for candidate in map:
                if candidate.startswith(wantType[:-1]):
                    subTypes = map[candidate]
                    if testType in subTypes:
                        return True
            return False
        else:            
            subTypes = map.get(wantType, [wantType])            
            return testType in subTypes
            
    def _makeClosure(self, map):
        #for each sub class, get its subclasses and append them
        def close(done, super, subs):
            done[super] = dict([(x,1) for x in subs]) #a set really
            for sub in subs:                
                if not sub in done:                    
                    close(done, sub, map[sub])                
                done[super].update(done[sub])

        closure = {}           
        for key, value in map.items():
            close(closure, key, value)
        return dict([(x, y.keys()) for x, y in closure.items()])

    def findStatements(self, uri, explicitStmts):
        stmts = []
        isProp = uri in self.currentSuperProperties
        isClass = uri in self.currentSuperTypes        
        if isProp or isClass:
            if RDF_MS_BASE+u'type' not in [x.predicate for x in stmts]:
                #no type statement, so add one now
                if isProp:
                    stmts.append( Statement(uri, RDF_MS_BASE+u'type',
                        RDF_MS_BASE+u'Property', objectType=OBJECT_TYPE_RESOURCE) )
                if isClass:
                    #print uri, stmts
                    stmts.append( Statement(uri, RDF_MS_BASE+u'type',
                        RDF_SCHEMA_BASE+u'Class', objectType=OBJECT_TYPE_RESOURCE) )
                    
        return stmts
    
    def addToSchema(self, stmts):
        self._beginTxn()
        
        propsChanged = False
        typesChanged = False

        #you can declare subproperties to rdf:type, rdfs:subClassPropOf, rdfs:subPropertyOf
        #but it will only take effect in the next call to addToSchema
        #also they can not be removed consistently
        #thus they should be declared in the initial schemas
        for stmt in stmts:
            if stmt.predicate in self.subPropPreds:
                self.currentSubProperties.setdefault(stmt.object, [stmt.object]).append(stmt.subject)
                #add this subproperty if this is the only reference to it so far
                self.currentSubProperties.setdefault(stmt.subject, [stmt.subject])

                self.currentSuperProperties.setdefault(stmt.subject, [stmt.subject]).append(stmt.object)
                #add this superproperty if this is the only reference to it so far
                self.currentSuperProperties.setdefault(stmt.object, [stmt.object])
                
                propsChanged = True
            elif stmt.predicate in self.subClassPreds:                
                self.currentSubTypes.setdefault(stmt.object, [stmt.object]).append(stmt.subject)
                #add this subclass if this is the only reference to it so far
                self.currentSubTypes.setdefault(stmt.subject, [stmt.subject])  

                self.currentSuperTypes.setdefault(stmt.subject, [stmt.subject]).append(stmt.object)
                #add this superclass if this is the only reference to it so far
                self.currentSuperTypes.setdefault(stmt.object, [stmt.object])
                
                typesChanged = True
            elif stmt.predicate in self.typePreds:
                self.currentSubTypes.setdefault(stmt.object, [stmt.object])
                self.currentSuperTypes.setdefault(stmt.object, [stmt.object])

                if self.isCompatibleType(stmt.object, RDF_SCHEMA_BASE+u'Class'):
                    self.currentSubTypes.setdefault(stmt.subject, [stmt.subject])
                    self.currentSuperTypes.setdefault(stmt.subject, [stmt.subject])
                elif self.isCompatibleType(stmt.object, RDF_MS_BASE+u'Property'):
                    self.currentSubProperties.setdefault(stmt.subject, [stmt.subject])
                    self.currentSuperProperties.setdefault(stmt.subject, [stmt.subject])
            else:
                self.currentSubProperties.setdefault(stmt.predicate, [stmt.predicate])
                self.currentSuperProperties.setdefault(stmt.predicate, [stmt.predicate])

        if typesChanged:
            self.currentSubTypes = self._makeClosure(self.currentSubTypes)
            if self.autocommit:
                self.subtypes = self.currentSubTypes
            
        if propsChanged:
            self.currentSubProperties = self._makeClosure(self.currentSubProperties)
            if self.autocommit:
                self.subproperties = self.currentSubProperties
        
            #just in case a subproperty of any of these were added
            self.subClassPreds = self.currentSubProperties[self.SUBCLASSOF]
            self.subPropPreds  = self.currentSubProperties[self.SUBPROPOF]
            self.typePreds     = self.currentSubProperties[RDF_MS_BASE+u'type']        
           
    def removeFromSchema(self, stmts):
        #todo: we don't remove resources from the properties or type dictionaries
        #(because its not clear when we can safely do that)
        #this means a formerly class or property resource can not be safely reused
        #as another type of resource without reloading the model
        self._beginTxn()
        
        propsChanged = False
        typesChanged = False

        for stmt in stmts:
            if stmt.predicate in self.subPropPreds:
                try:
                    self.currentSubProperties[stmt.object].remove(stmt.subject)
                    self.currentSuperProperties[stmt.subject].remove(stmt.object)
                except KeyError, ValueError:
                    pass#todo warn if not found                
                propsChanged = True

            if stmt.predicate in self.subClassPreds:
                try: 
                    self.currentSubTypes[stmt.object].remove(stmt.subject)
                    self.currentSuperTypes[stmt.subject].remove(stmt.object)
                except KeyError, ValueError:
                    pass#todo warn if not found                
                typesChanged = True            

        if typesChanged:
            newsubtypes = {}
            for k, v in self.currentSuperTypes.items():
                for supertype in v:
                    newsubtypes.setdefault(supertype, []).append(k)

            self.currentSubTypes = self._makeClosure(newsubtypes)
            if self.autocommit:
                self.subtypes = self.currentSubTypes
            
        if propsChanged:
            newsubprops = {}
            for k, v in self.currentSuperProperties.items():
                for superprop in v:
                    newsubprops.setdefault(superprop, []).append(k)
            
            self.currentSubProperties = self._makeClosure(newsubprops)
            if self.autocommit:
                self.subproperties = self.currentSubProperties

            #just in case a subproperty of any of these were removed
            self.subClassPreds = self.currentSubProperties[self.SUBCLASSOF]
            self.subPropPreds  = self.currentSubProperties[self.SUBPROPOF]
            self.typePreds     = self.currentSubProperties[RDF_MS_BASE+u'type']        
        
    def _beginTxn(self): 
        if not self.autocommit and not self.inTransaction:
            self.currentSubProperties = copy.deepcopy(self.subproperties)
            self.currentSubTypes = copy.deepcopy(self.subtypes)
            self.currentSuperProperties = copy.deepcopy(self.superproperties)
            self.currentSuperTypes = copy.deepcopy(self.supertypes)

            self.inTransaction = True
            
    def commit(self, **kw):
        if self.autocommit:
            return
        self.subproperties = self.currentSubProperties        
        self.subtypes = self.currentSubTypes
        self.superproperties = self.currentSuperProperties
        self.supertypes = self.currentSuperTypes 
        
        self.inTransaction = False
        
    def rollback(self):
        self.currentSubProperties = self.subproperties
        self.currentSubTypes = self.subtypes
        self.currentSuperProperties = self.superproperties
        self.currentSuperTypes = self.supertypes

        #just in case a subproperty of any of these changed
        self.subClassPreds = self.currentSubProperties[self.SUBCLASSOF]
        self.subPropPreds  = self.currentSubProperties[self.SUBPROPOF]
        self.typePreds     = self.currentSubProperties[RDF_MS_BASE+u'type']        

        self.inTransaction = False
        
#_baseSchema = RDFSSchema()            