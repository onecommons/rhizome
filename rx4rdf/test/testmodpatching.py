import rx.RxPath
import Ft.Xml.XPath.ParsedAxisSpecifier
assert Ft.Xml.XPath.ParsedAxisSpecifier.AxisSpecifier.descendants.im_func is rx.RxPath.descendants
print 'success!',rx.RxPath.descendants, 'is', Ft.Xml.XPath.ParsedAxisSpecifier.AxisSpecifier.descendants