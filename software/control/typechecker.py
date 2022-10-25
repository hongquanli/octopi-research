from typing import Union, Optional, List, TypeVar, Generic
NoneType=type(None)
from dataclasses import Field

def is_protected_symbol(symbol:str)->bool:
    return len(symbol)>4 and symbol[:2]=="__" and symbol[-2:]=="__"

class TypeCheckResult:
    def __init__(self,val:bool,msg:str=""):
        self.val=val
        self.msg=msg
    def __bool__(self)->bool:
        return self.val

# compared expected to value type
def type_match(et,v):
    vt=type(v)
    if et==vt:
        return TypeCheckResult(True)

    if vt==Field:
        return TypeCheckResult(True)
    
    # check for unions
    try:
        et_type_is_union=et.__origin__==Union
        et_type_is_list=et.__origin__==list
    except:
        et_type_is_union=False
        et_type_is_list=False

    if et_type_is_union:
        for arg in et.__args__:
            if type_match(arg,v):
                return TypeCheckResult(True)

        return TypeCheckResult(False)
    elif et_type_is_list:
        if list!=vt:
            return TypeCheckResult(False,msg=f"{vt} is not a list")

        for i,v in enumerate(v):
            et_list_item_type=et.__args__[0]
            if not type_match(et_list_item_type,v):
                et_list_item_type_name=et_list_item_type
                try:
                    et_list_item_type_name=et_list_item_type_name.__name__
                except:
                    et_list_item_type_name=str(et_list_item_type_name)

                return TypeCheckResult(False,msg=f"list item type mismatch {et_list_item_type_name} != {type(v)} at index {i}")

        return TypeCheckResult(True)

    try:
        et_type_is_closed_range=et.__orig_class__.__origin__==ClosedRange
    except:
        et_type_is_closed_range=False

    if et_type_is_closed_range:
        tmr=type_match(et.__orig_class__.arg,v)
        if not tmr:
            return tmr

        try:
            if et.lb_incl:
                assert et.lower<=v
            else:
                assert et.lower<v
        except:
            return TypeCheckResult(False,msg="lower bound exceeded")

        try:
            if et.ub_incl:
                assert et.upper>=v
            else:
                assert et.upper>v
        except:
            return TypeCheckResult(False,msg="upper bound exceeded")

        return TypeCheckResult(True)

    et_name=et
    try:
        et_name=et_name.__name__
    except:
        et_name=str(et_name)

    vt_name=vt
    try:
        vt_name=vt_name.__name__
    except:
        vt_name=str(vt_name)

    return TypeCheckResult(False,msg=f"{et_name}!={vt_name} (generic)")

# decorator that serves as type checker for classes
def Typecheck(_t:Optional=None,*,check_defaults:bool=True,create_init:bool=False,create_str:bool=False):
    def inner(t):
        t_attributes={}

        sorted_keys=sorted(list(t.__dict__.keys()))

        for k,v in t.__annotations__.items():
            t_attributes[k]=v

        # check default value type match
        if check_defaults:
            for symbol in sorted_keys:
                if is_protected_symbol(symbol):
                    continue

                if callable(t.__dict__[symbol]):
                    continue

                if not symbol in t.__annotations__:
                    raise TypeError(f"no type annotation for {t.__name__}.{symbol}")

                annotated_type=t.__annotations__[symbol]
                t_attributes[symbol]=annotated_type

                try:
                    default_value=t.__dict__[symbol]
                except:
                    raise Exception("unimplemented")

                type_match_check=type_match(annotated_type,default_value)
                if not type_match_check:
                    raise TypeError(f"type mismatch in {t.__name__}.{symbol}: {type_match_check.msg}")

        t_attributes_sorted=sorted(list(t_attributes.keys()))

        # create __init__ method for class t
        if create_init:
            if "__init__" in t.__dict__:
                raise ValueError(f"init method already present for {t}")

            def init(s,*args,**kwargs):
                # keep track of already initialized fields to avoid overlap
                already_initialized_fields={
                    k:False
                    for k in t_attributes
                }

                def attribute_type_check_failure(a,k,type_match_check:TypeCheckResult):
                    type_a_name=type(a)
                    type_t_name=t
                    type_k_expcted_type_name=k_expected_type

                    try:
                        type_a_name=type_a_name.__name__
                    except:
                        type_a_name=str(type_a_name)

                    try:
                        type_t_name=type_t_name.__name__
                    except:
                        type_t_name=str(type_t_name)

                    try:
                        type_k_expcted_type_name=type_k_expcted_type_name.__name__
                    except:
                        type_k_expcted_type_name=str(type_k_expcted_type_name)

                    raise ValueError(f"value {a}:{type_a_name} cannot be assigned to {type_t_name}.{k}:{type_k_expcted_type_name} because {type_match_check.msg}")


                # iterate over positional args to __init__
                for i,a in enumerate(args):
                    k=t_attributes_sorted[i]
                    k_expected_type=t_attributes[k]

                    type_match_check=type_match(k_expected_type,a)
                    if not type_match_check:
                        attribute_type_check_failure(a,k,type_match_check)
                    s.__dict__[k]=a
                    already_initialized_fields[k]=True

                # iterate over keyword args to __init__
                for k,a in kwargs.items():
                    if not k in t_attributes:
                        raise ValueError(f"field {k} does not exist in {t}")

                    if already_initialized_fields[k]:
                        raise ValueError(f"field {k} already initialized as positional argument")

                    k_expected_type=t_attributes[k]
                    type_match_check=type_match(k_expected_type,a)
                    if not type_match_check:
                        attribute_type_check_failure(a,k,type_match_check)

                    s.__dict__[k]=a

            t.__init__=init
        
        if create_str:
            if "__str__" in t.__dict__:
                raise ValueError(f"str method already present for {t}")

            def as_string(s)->str:
                ret=f"{t.__name__}( "
                for k,v in t_attributes.items():
                    if is_protected_symbol(k):
                        continue
                    
                    v_name=v
                    try:
                        v_name=v.__name__
                    except:
                        v_name=str(v_name)

                    ret+=f"{k}: {v_name} = {s.__getattribute__(k)}, "

                if ret[-1]!="(":
                    ret=ret[:-2]
                
                return ret+" )"

            t.__str__=as_string

        return t

    if _t is None:
        return inner
    else:
        return inner(_t)

import typing

T=TypeVar("T")
NO_ARG=object()
class ClosedRange(Generic[T]):
    # lower limit
    lower:T
    # upper limit
    upper:T
    # lower bound inclusive
    lb_incl:bool
    # upper bound inclusive
    ub_incl:bool

    # from https://stackoverflow.com/a/69129940
    arg = NO_ARG  # using `arg` to store the current type argument

    def __class_getitem__(cls, key):
        if cls.arg is NO_ARG or cls.arg is T:
            cls.arg = key 
        else:
            try:
                cls.arg = cls.arg[key]
            except TypeError:
                cls.arg = key
        return super().__class_getitem__(key)

    def __init_subclass__(cls):
        if Parent.arg is not NO_ARG:
            cls.arg, Parent.arg = Parent.arg, NO_ARG

    def __init__(self,lower:T,upper:T,lb_incl:bool=True,ub_incl:bool=True):
        assert lower<upper

        tmr=type_match(self.arg,lower)
        assert tmr,f"lower bound invalid {tmr.msg}"

        tmr=type_match(self.arg,upper)
        assert tmr,f"upper bound invalid {tmr.msg}"

        self.lower=lower
        self.upper=upper

        self.lb_incl=lb_incl
        self.ub_incl=ub_incl

    def __str__(self):
        return f"ClosedRange[ {self.lower} {'<=' if self.lb_incl else '<'} float {'>=' if self.ub_incl else '>'} {self.upper} ]"

if __name__=="__main__":

    assert     type_match(int,3)
    assert not type_match(int,3.0)
    assert not type_match(float,3)

    assert     type_match(Union[int,float],3)
    assert     type_match(Union[int,float],3.0)
    assert not type_match(Union[int,float],None)

    assert     type_match(Optional[int],None)
    assert     type_match(Optional[int],3)

    assert     type_match(list,[3.0])
    assert not type_match(List[int],[3.0])
    assert not type_match(List[int],[3,3.0])
    assert not type_match(List[Optional[float]],[3.0,None,2])
    assert     type_match(List[Optional[float]],[3.0,None,2.0])

    @Typecheck(create_str=True)
    class B:
        a:int=3
        c:float=2.0
        d:Union[float,int]=3.0
        e:List[float]=[2.0,3.0]

    @Typecheck(create_init=True,create_str=True)
    class C:
        a:int=3
        c:float=2.0
        d:Union[float,int]=3.0
        e:List[float]=[2.0,3.0]

    b=B()
    print(b)

    c=C()
    print(c)
    c=C(2,3.0,d=3,e=[3.0])
    print(c)

    @Typecheck(create_init=True,create_str=True)
    class TestRange:
        vt:ClosedRange[float](1.0,2.0)

    tr=TestRange(vt=1.5)
    print(tr)
