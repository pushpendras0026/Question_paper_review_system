import pymysql

# Make pymysql masquerade as mysqlclient so Django's mysql backend accepts it.
# Django 6.x checks for mysqlclient >= 2.2.1; we tell it pymysql satisfies that.
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()
