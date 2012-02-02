=====
PyBBS
=====

Python implementation of the KBS bulletin board system

Currently it is just partial implementation. So it need to work alongside the KBS system.

It provides 

* Data interface
	It supports listing boards, listing posts, and reading posts currently.
	It will support other features in the future.

* XMPP interface
	It supports communications between users, adding/removing friends, getting friends list, and other features.

It is under development, and new features are being added.

Maybe one day this project can operate without the original KBS system.

It is licensed under the 2-clause BSD License, a.k.a. Simplified BSD License.

For the xmpp part, the source is modified from the python-xmpp-server_ project on github. Its license is in the xmpp/LICENSE file.

It depends on python-sasl_, tornado_ and lxml_.

.. _python-xmpp-server: http://github.com/thisismedium/python-xmpp-server
.. _tornado: http://github.com/facebook/tornado
.. _lxml: http://lxml.de
