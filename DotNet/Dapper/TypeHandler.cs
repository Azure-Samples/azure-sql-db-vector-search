using Microsoft.Data.SqlClient;
using Dapper;
using Microsoft.Data.SqlTypes;
using Microsoft.Data;

public class VectorTypeHandler: SqlMapper.TypeHandler<float[]>
{
    public override float[] Parse(object value)
    {
        return ((SqlVector<float>)value).Memory.ToArray();
    }

    public override void SetValue(System.Data.IDbDataParameter parameter, float[]? value)
    {
        parameter.Value = value is not null ? new SqlVector<float>(value) : DBNull.Value;
        ((SqlParameter)parameter).SqlDbType = SqlDbTypeExtensions.Vector;
    }
}
